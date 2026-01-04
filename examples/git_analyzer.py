# Git Analyzer - Correlates failures with recent code changes
# Save as git_analyzer.py

import subprocess
import logging
from datetime import datetime, timedelta
import json
import os

logging.basicConfig(level=logging.INFO)

class GitAnalyzer:
    def __init__(self, repo_path):
        self.repo_path = repo_path
        if not os.path.exists(os.path.join(repo_path, '.git')):
            raise ValueError(f"Not a git repository: {repo_path}")
    
    def _run_git_command(self, command):
        """Execute a git command and return output"""
        try:
            result = subprocess.run(
                command,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logging.error(f"Git command failed: {e.stderr}")
            return None
    
    def get_recent_commits(self, service_path=None, hours=24, limit=10):
        """Get recent commits, optionally filtered by service path"""
        since_time = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        
        cmd = [
            "git", "log",
            f"--since={since_time}",
            f"-{limit}",
            "--pretty=format:%H|%an|%ae|%ad|%s",
            "--date=iso"
        ]
        
        if service_path:
            cmd.append("--")
            cmd.append(service_path)
        
        output = self._run_git_command(cmd)
        if not output:
            return []
        
        commits = []
        for line in output.split('\n'):
            if not line:
                continue
            parts = line.split('|', 4)
            if len(parts) == 5:
                commits.append({
                    "hash": parts[0],
                    "author": parts[1],
                    "email": parts[2],
                    "date": parts[3],
                    "message": parts[4]
                })
        
        return commits
    
    def get_commit_details(self, commit_hash):
        """Get detailed information about a specific commit"""
        cmd = ["git", "show", "--stat", commit_hash]
        output = self._run_git_command(cmd)
        
        if not output:
            return None
        
        # Parse commit info
        lines = output.split('\n')
        commit_info = {
            "hash": commit_hash,
            "full_output": output,
            "files_changed": []
        }
        
        # Extract changed files
        for line in lines:
            if '|' in line and ('+' in line or '-' in line):
                parts = line.split('|')
                if len(parts) >= 2:
                    commit_info["files_changed"].append(parts[0].strip())
        
        return commit_info
    
    def get_file_history(self, file_path, limit=5):
        """Get commit history for a specific file"""
        cmd = [
            "git", "log",
            f"-{limit}",
            "--pretty=format:%H|%an|%ad|%s",
            "--date=short",
            "--",
            file_path
        ]
        
        output = self._run_git_command(cmd)
        if not output:
            return []
        
        commits = []
        for line in output.split('\n'):
            if not line:
                continue
            parts = line.split('|', 3)
            if len(parts) == 4:
                commits.append({
                    "hash": parts[0],
                    "author": parts[1],
                    "date": parts[2],
                    "message": parts[3]
                })
        
        return commits
    
    def get_changed_files_in_commit(self, commit_hash):
        """Get list of files changed in a commit"""
        cmd = ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit_hash]
        output = self._run_git_command(cmd)
        
        if not output:
            return []
        
        return [f.strip() for f in output.split('\n') if f.strip()]
    
    def find_commits_by_file_pattern(self, pattern, hours=168):
        """Find commits that modified files matching a pattern (e.g., 'payment*.java')"""
        since_time = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        
        cmd = [
            "git", "log",
            f"--since={since_time}",
            "--pretty=format:%H|%an|%ad|%s",
            "--date=short",
            "--name-only"
        ]
        
        output = self._run_git_command(cmd)
        if not output:
            return []
        
        commits = []
        current_commit = None
        
        for line in output.split('\n'):
            if not line:
                continue
            
            if '|' in line:
                # New commit header
                parts = line.split('|', 3)
                if len(parts) == 4:
                    current_commit = {
                        "hash": parts[0],
                        "author": parts[1],
                        "date": parts[2],
                        "message": parts[3],
                        "files": []
                    }
                    commits.append(current_commit)
            elif current_commit:
                # File name
                if pattern in line:
                    current_commit["files"].append(line.strip())
        
        # Filter commits that actually match the pattern
        return [c for c in commits if c.get("files")]
    
    def get_deployment_correlation(self, service_name, hours=24):
        """
        Get deployment events by looking for commits with deployment-related keywords
        (In production, this should integrate with your CI/CD system)
        """
        since_time = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        
        keywords = ["deploy", "release", "version", "production"]
        cmd = [
            "git", "log",
            f"--since={since_time}",
            "--pretty=format:%H|%an|%ad|%s",
            "--date=iso",
            f"--grep={'|'.join(keywords)}",
            "--regexp-ignore-case"
        ]
        
        output = self._run_git_command(cmd)
        if not output:
            return []
        
        deployments = []
        for line in output.split('\n'):
            if not line:
                continue
            parts = line.split('|', 3)
            if len(parts) == 4:
                deployments.append({
                    "hash": parts[0],
                    "author": parts[1],
                    "date": parts[2],
                    "message": parts[3],
                    "service": service_name
                })
        
        return deployments


# Example usage
if __name__ == "__main__":
    # Test with current repository
    analyzer = GitAnalyzer("/home/sakthi/PROJECTS/ccp")
    
    print("Recent commits (last 24 hours):")
    commits = analyzer.get_recent_commits(hours=24, limit=5)
    for commit in commits:
        print(f"  {commit['hash'][:8]} - {commit['author']}: {commit['message']}")
    
    if commits:
        print(f"\nDetails for first commit:")
        details = analyzer.get_commit_details(commits[0]['hash'])
        print(f"  Files changed: {details['files_changed']}")
