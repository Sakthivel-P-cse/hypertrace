"""
Patch Applier
Applies code patches to files and manages Git operations (commits, rollbacks).
"""

import os
import re
import subprocess
import tempfile
import shutil
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
import difflib


@dataclass
class PatchResult:
    """Result of applying a patch"""
    success: bool
    file_path: str
    lines_added: int
    lines_removed: int
    diff: str
    commit_hash: Optional[str] = None
    error: Optional[str] = None


class PatchApplier:
    """
    Applies code patches to files with Git integration.
    
    Features:
    - Dry-run mode for testing
    - Automatic Git commits
    - Rollback support
    - Backup creation
    - Unified diff generation
    """
    
    def __init__(self, repo_path: str, config: Optional[Dict[str, Any]] = None):
        self.repo_path = Path(repo_path)
        self.config = config or {}
        
        self.auto_commit = self.config.get('auto_commit', True)
        self.create_backups = self.config.get('create_backups', True)
        self.backup_dir = self.repo_path / '.patch_backups'
        
        # Ensure backup directory exists
        if self.create_backups:
            self.backup_dir.mkdir(exist_ok=True)
        
        # Check if repo is a Git repository
        self.is_git_repo = self._check_git_repo()
    
    def _check_git_repo(self) -> bool:
        """Check if the repository path is a Git repository"""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--is-inside-work-tree'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    def apply_patch(
        self,
        file_path: str,
        original_content: str,
        patched_content: str,
        dry_run: bool = False,
        commit_message: Optional[str] = None
    ) -> PatchResult:
        """
        Apply a patch to a file.
        
        Args:
            file_path: Relative path to file from repo root
            original_content: Original file content
            patched_content: Content after patch
            dry_run: If True, don't actually modify files
            commit_message: Git commit message
            
        Returns:
            PatchResult with details of the operation
        """
        full_path = self.repo_path / file_path
        
        # Verify original content matches
        if full_path.exists():
            current_content = full_path.read_text(encoding='utf-8')
            if current_content != original_content:
                return PatchResult(
                    success=False,
                    file_path=file_path,
                    lines_added=0,
                    lines_removed=0,
                    diff="",
                    error="Original content doesn't match current file content"
                )
        
        # Generate diff
        diff = self._generate_diff(original_content, patched_content, file_path)
        
        # Count changes
        lines_added, lines_removed = self._count_changes(original_content, patched_content)
        
        if dry_run:
            return PatchResult(
                success=True,
                file_path=file_path,
                lines_added=lines_added,
                lines_removed=lines_removed,
                diff=diff
            )
        
        # Create backup
        backup_path = None
        if self.create_backups and full_path.exists():
            backup_path = self._create_backup(full_path)
        
        try:
            # Ensure parent directory exists
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write patched content
            full_path.write_text(patched_content, encoding='utf-8')
            
            # Git commit if enabled
            commit_hash = None
            if self.auto_commit and self.is_git_repo:
                commit_hash = self._git_commit(
                    file_path,
                    commit_message or f"Auto-fix: {file_path}"
                )
            
            return PatchResult(
                success=True,
                file_path=file_path,
                lines_added=lines_added,
                lines_removed=lines_removed,
                diff=diff,
                commit_hash=commit_hash
            )
            
        except Exception as e:
            # Restore from backup on failure
            if backup_path and backup_path.exists():
                shutil.copy2(backup_path, full_path)
            
            return PatchResult(
                success=False,
                file_path=file_path,
                lines_added=0,
                lines_removed=0,
                diff=diff,
                error=str(e)
            )
    
    def apply_batch(
        self,
        patches: List[Dict[str, Any]],
        dry_run: bool = False,
        commit_message: Optional[str] = None
    ) -> List[PatchResult]:
        """
        Apply multiple patches as a batch.
        
        Args:
            patches: List of patch dicts with 'file_path', 'original', 'patched'
            dry_run: If True, don't actually modify files
            commit_message: Single commit message for all patches
            
        Returns:
            List of PatchResult objects
        """
        results = []
        
        for patch in patches:
            result = self.apply_patch(
                patch['file_path'],
                patch['original'],
                patch['patched'],
                dry_run=dry_run,
                commit_message=None  # We'll commit all at once
            )
            results.append(result)
            
            # Stop on first failure
            if not result.success:
                break
        
        # If all succeeded and not dry run, make a single commit
        if not dry_run and all(r.success for r in results):
            if self.auto_commit and self.is_git_repo:
                file_paths = [r.file_path for r in results]
                commit_hash = self._git_commit_multiple(
                    file_paths,
                    commit_message or f"Auto-fix: {len(file_paths)} files"
                )
                # Update all results with commit hash
                for result in results:
                    result.commit_hash = commit_hash
        
        return results
    
    def rollback(self, commit_hash: str) -> bool:
        """
        Rollback to a previous commit.
        
        Args:
            commit_hash: Git commit hash to rollback to
            
        Returns:
            True if successful
        """
        if not self.is_git_repo:
            return False
        
        try:
            subprocess.run(
                ['git', 'revert', '--no-edit', commit_hash],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )
            return True
        except:
            return False
    
    def rollback_last_n(self, n: int = 1) -> bool:
        """
        Rollback the last N commits.
        
        Args:
            n: Number of commits to rollback
            
        Returns:
            True if successful
        """
        if not self.is_git_repo:
            return False
        
        try:
            subprocess.run(
                ['git', 'reset', '--hard', f'HEAD~{n}'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )
            return True
        except:
            return False
    
    def _generate_diff(
        self,
        original: str,
        patched: str,
        file_path: str
    ) -> str:
        """Generate unified diff"""
        original_lines = original.splitlines(keepends=True)
        patched_lines = patched.splitlines(keepends=True)
        
        diff_lines = difflib.unified_diff(
            original_lines,
            patched_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm=''
        )
        
        return ''.join(diff_lines)
    
    def _count_changes(self, original: str, patched: str) -> Tuple[int, int]:
        """Count lines added and removed"""
        original_lines = set(original.splitlines())
        patched_lines = set(patched.splitlines())
        
        lines_added = len(patched_lines - original_lines)
        lines_removed = len(original_lines - patched_lines)
        
        return lines_added, lines_removed
    
    def _create_backup(self, file_path: Path) -> Path:
        """Create a backup of a file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.name}.{timestamp}.backup"
        backup_path = self.backup_dir / backup_name
        
        shutil.copy2(file_path, backup_path)
        return backup_path
    
    def _git_commit(self, file_path: str, message: str) -> Optional[str]:
        """Commit a single file to Git"""
        try:
            # Stage the file
            subprocess.run(
                ['git', 'add', file_path],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
                timeout=10
            )
            
            # Commit
            subprocess.run(
                ['git', 'commit', '-m', message],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
                timeout=10
            )
            
            # Get commit hash
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
                timeout=5
            )
            
            return result.stdout.strip()
            
        except subprocess.CalledProcessError:
            return None
    
    def _git_commit_multiple(
        self,
        file_paths: List[str],
        message: str
    ) -> Optional[str]:
        """Commit multiple files to Git"""
        try:
            # Stage all files
            for file_path in file_paths:
                subprocess.run(
                    ['git', 'add', file_path],
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=10
                )
            
            # Commit
            subprocess.run(
                ['git', 'commit', '-m', message],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
                timeout=10
            )
            
            # Get commit hash
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
                timeout=5
            )
            
            return result.stdout.strip()
            
        except subprocess.CalledProcessError:
            return None
    
    def get_commit_info(self, commit_hash: str) -> Optional[Dict[str, Any]]:
        """Get information about a commit"""
        if not self.is_git_repo:
            return None
        
        try:
            result = subprocess.run(
                ['git', 'show', '--no-patch', '--format=%H%n%an%n%ae%n%ad%n%s', commit_hash],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
                timeout=5
            )
            
            lines = result.stdout.strip().split('\n')
            return {
                'hash': lines[0],
                'author_name': lines[1],
                'author_email': lines[2],
                'date': lines[3],
                'message': lines[4]
            }
        except:
            return None


# Example usage
if __name__ == "__main__":
    # Create a test directory
    test_dir = Path(tempfile.mkdtemp())
    test_file = test_dir / "example.py"
    
    print(f"Test directory: {test_dir}")
    
    # Initialize Git repo
    subprocess.run(['git', 'init'], cwd=test_dir, capture_output=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=test_dir, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=test_dir, capture_output=True)
    
    # Create original file
    original = '''def process(data):
    return data.upper()

def main():
    print(process("hello"))
'''
    
    test_file.write_text(original)
    subprocess.run(['git', 'add', 'example.py'], cwd=test_dir, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'Initial commit'], cwd=test_dir, capture_output=True)
    
    # Create patched version
    patched = '''def process(data):
    if data is None:
        return ""
    return data.upper()

def main():
    result = process("hello")
    print(f"Result: {result}")
'''
    
    # Apply patch
    applier = PatchApplier(str(test_dir), {
        'auto_commit': True,
        'create_backups': True
    })
    
    # Dry run first
    print("\n=== DRY RUN ===")
    result = applier.apply_patch(
        "example.py",
        original,
        patched,
        dry_run=True
    )
    
    print(f"Success: {result.success}")
    print(f"Lines added: {result.lines_added}")
    print(f"Lines removed: {result.lines_removed}")
    print("\nDiff:")
    print(result.diff)
    
    # Apply for real
    print("\n=== APPLYING PATCH ===")
    result = applier.apply_patch(
        "example.py",
        original,
        patched,
        dry_run=False,
        commit_message="Fix: Add null check to process()"
    )
    
    print(f"Success: {result.success}")
    print(f"Commit: {result.commit_hash}")
    
    if result.commit_hash:
        commit_info = applier.get_commit_info(result.commit_hash)
        print(f"Commit info: {commit_info}")
    
    # Verify file was updated
    updated_content = test_file.read_text()
    print(f"\nFile updated: {updated_content == patched}")
    
    # Cleanup
    shutil.rmtree(test_dir)
    print(f"\nCleaned up test directory")
