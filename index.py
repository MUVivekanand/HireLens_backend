import asyncio
import json
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from agents import create_mcp_agent
from utils import run_mcp_agent
import githubmcp  # Import the module to patch it

app = Flask(__name__)
CORS(app)

# Global variable to store current token (thread-safe for single request processing)
_current_github_token = None

def set_github_token(token: str):
    """Set the GitHub token for the current request."""
    global _current_github_token
    _current_github_token = token
    # Also set in environment as backup
    os.environ['GITHUB_TOKEN'] = token

def get_github_token():
    """Get the current GitHub token."""
    global _current_github_token
    if _current_github_token:
        return _current_github_token
    return os.getenv("GITHUB_TOKEN")

# Monkey patch the githubmcp module to use our token getter
original_make_request = githubmcp.make_github_request

def patched_make_request(endpoint: str, method: str = "GET", token: str = None):
    """Patched version that uses current token if none provided."""
    if token is None:
        token = get_github_token()
    return original_make_request(endpoint, method, token)

githubmcp.make_github_request = patched_make_request

@app.route('/api/analyze-contribution', methods=['POST'])
def analyze_contribution():
    global _current_github_token
    
    try:
        # Get JSON data from request
        data = request.get_json()
        
        # Extract fields
        project = data.get('project')
        author = data.get('author')
        owner = data.get('owner')
        github_token = data.get('github_token')
        
        # Validate required fields
        if not all([project, author, owner]):
            return jsonify({
                "success": False,
                "error": "Missing required fields: project, author, and owner are required"
            }), 400
        
        # Print received data (mask token for security)
        print("=" * 50)
        print("Received JSON Data:")
        print(f"Project: {project}")
        print(f"Author: {author}")
        print(f"Owner: {owner}")
        if github_token:
            print(f"GitHub Token: {'*' * 20}{github_token[-4:] if len(github_token) > 4 else '****'}")
        else:
            print("GitHub Token: Using .env token")
        print("=" * 50)
        
        # Set the GitHub token for this request
        if github_token:
            set_github_token(github_token)
        
        # Initialize agent if needed
        mcp_agent = asyncio.run(create_mcp_agent())
        
        # Create task for the agent
        task = f"Analyze GitHub contributions for {author} in the {owner}/{project} repository"
        
        # Run the async agent function synchronously
        result = asyncio.run(run_mcp_agent(mcp_agent, task))
        print("Result to frontend:", result)
        
        # Clean up
        _current_github_token = None
        if github_token and 'GITHUB_TOKEN' in os.environ:
            # Restore original .env token if it exists
            from dotenv import load_dotenv
            load_dotenv(override=True)
        
        # Return the result
        return jsonify(result), 200
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Clean up token on error too
        _current_github_token = None
            
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "Backend is running"}), 200

@app.route('/debug', methods=['GET'])
def debug_info():
    import sys
    return jsonify({
        "python_executable": sys.executable,
        "python_version": sys.version,
        "python_path": sys.path,
        "cwd": os.getcwd(),
        "env_vars": {
            "GITHUB_TOKEN": "***" if os.getenv("GITHUB_TOKEN") else None,
            "GITHUB_API_BASE": os.getenv("GITHUB_API_BASE")
        }
    }), 200

if __name__ == "__main__":
    app.run(debug=True, port=8765, host='localhost')