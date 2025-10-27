import tempfile
import shutil
from typing import TypedDict, List, Optional, Dict, Any
import os
from fastmcp import FastMCP
import requests
import subprocess
from dotenv import load_dotenv

load_dotenv()

mcp = FastMCP(name="GitHub Tools Integration")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_API_BASE = os.getenv("GITHUB_API_BASE")

print(f"Using GitHub API Base:", GITHUB_API_BASE)
print(f"Using GitHub Token:", GITHUB_TOKEN)


def make_github_request(endpoint: str, method: str = "GET") -> Dict[Any, Any]:
    """Make authenticated GitHub API request."""
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "MCP-Git-Tool"
    }
    url = f"{GITHUB_API_BASE}/{endpoint.lstrip('/')}"
    response = requests.request(method, url, headers=headers)
    response.raise_for_status()
    return response.json()


def clone_repo_temp(repo_url: str, branch: str = "main") -> str:
    """Clone repository to temporary directory."""
    temp_dir = tempfile.mkdtemp()
    try:
        cmd = ["git", "clone", "--depth", "50", "-b", branch, repo_url, temp_dir]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return temp_dir
    except subprocess.CalledProcessError as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise Exception(f"Failed to clone repository: {e.stderr}")


# TypedDict classes for structured responses
class CommitInfo(TypedDict):
    """Commit information structure."""
    sha: str
    message: str
    author: str
    date: str
    url: str


class FileChange(TypedDict):
    """File change information."""
    filename: str
    status: str
    additions: int
    deletions: int
    patch: Optional[str]


class CommitDiff(TypedDict):
    """Complete commit diff information."""
    commit: CommitInfo
    files: List[FileChange]
    total_additions: int
    total_deletions: int


class RepoInfo(TypedDict):
    """Repository information."""
    name: str
    full_name: str
    description: Optional[str]
    default_branch: str
    clone_url: str
    updated_at: str


class BranchInfo(TypedDict):
    """Branch information structure."""
    name: str
    sha: str
    protected: bool


@mcp.tool()
def get_latest_commit(owner: str, repo: str, branch: str = "main") -> dict:
    """Get the latest commit from a repository branch."""
    try:
        data = make_github_request(f"repos/{owner}/{repo}/commits/{branch}")
        return {
            "sha": data["sha"],
            "message": data["commit"]["message"],
            "author": data["commit"]["author"]["name"],
            "date": data["commit"]["author"]["date"],
            "url": data["html_url"]
        }
    except Exception as e:
        raise Exception(f"Failed to get latest commit: {str(e)}")


@mcp.tool()
def get_commit_diff(owner: str, repo: str, commit_sha: str) -> dict:
    """Get detailed diff for a specific commit."""
    try:
        commit_data = make_github_request(f"repos/{owner}/{repo}/commits/{commit_sha}")
        
        commit_info = {
            "sha": commit_data["sha"],
            "message": commit_data["commit"]["message"],
            "author": commit_data["commit"]["author"]["name"],
            "date": commit_data["commit"]["author"]["date"],
            "url": commit_data["html_url"]
        }
        
        files = []
        total_additions = 0
        total_deletions = 0
        
        for file_data in commit_data.get("files", []):
            file_change = {
                "filename": file_data["filename"],
                "status": file_data["status"],
                "additions": file_data.get("additions", 0),
                "deletions": file_data.get("deletions", 0),
                "patch": file_data.get("patch", "")
            }
            files.append(file_change)
            total_additions += file_change["additions"]
            total_deletions += file_change["deletions"]
        
        return {
            "commit": commit_info,
            "files": files,
            "total_additions": total_additions,
            "total_deletions": total_deletions
        }
    except Exception as e:
        raise Exception(f"Failed to get commit diff: {str(e)}")


@mcp.tool()
def get_recent_commits(owner: str, repo: str, count: int = 10, branch: str = "main") -> List[dict]:
    """Get recent commits from a repository."""
    try:
        data = make_github_request(f"repos/{owner}/{repo}/commits?sha={branch}&per_page={count}")
        commits = []
        
        for commit_data in data:
            commit = {
                "sha": commit_data["sha"],
                "message": commit_data["commit"]["message"],
                "author": commit_data["commit"]["author"]["name"],
                "date": commit_data["commit"]["author"]["date"],
                "url": commit_data["html_url"]
            }
            commits.append(commit)
        
        return commits
    except Exception as e:
        raise Exception(f"Failed to get recent commits: {str(e)}")


@mcp.tool()
def get_file_content(owner: str, repo: str, file_path: str, branch: str = "main") -> dict:
    """Get content of a specific file from repository."""
    try:
        data = make_github_request(f"repos/{owner}/{repo}/contents/{file_path}?ref={branch}")
        
        if data.get("type") != "file":
            raise Exception(f"Path {file_path} is not a file")
        
        import base64
        content = base64.b64decode(data["content"]).decode('utf-8')
        
        return {
            "path": file_path,
            "content": content,
            "sha": data["sha"],
            "size": data["size"],
            "download_url": data.get("download_url", "")
        }
    except Exception as e:
        raise Exception(f"Failed to get file content: {str(e)}")


if __name__ == "__main__":
    mcp.run(transport="stdio")