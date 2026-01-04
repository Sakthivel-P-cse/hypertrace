"""
Linter Runner with Change-Aware Checking
Runs linters only on changed files and filters new issues.
Implements Change-Aware Safety Gates (Improvement #1).
"""

import subprocess
import re
import json
from typing import Dict, List, Any, Optional, Set
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum


class IssueSeverity(Enum):
    """Lint issue severity levels"""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    STYLE = "style"


@dataclass
class LintIssue:
    """A single lint issue"""
    file_path: str
    line_number: int
    column: Optional[int]
    severity: IssueSeverity
    rule: str
    message: str
    linter: str


@dataclass
class LintResult:
    """Result of linting"""
    passed: bool
    linter: str
    files_checked: int
    total_issues: int
    errors: int
    warnings: int
    info: int
    issues: List[LintIssue]
    changed_files_only: bool
    new_issues_only: bool
    duration_seconds: float


class LinterRunner:
    """
    Runs linters with change-aware checking.
    Only lints changed files and filters for new issues.
    """
    
    def __init__(self, project_path: str, config: Optional[Dict[str, Any]] = None):
        self.project_path = Path(project_path)
        self.config = config or {}
        
        self.max_errors = self.config.get('max_errors', 0)
        self.max_warnings = self.config.get('max_warnings', 50)
        self.fail_on_error = self.config.get('fail_on_error', True)
        self.timeout = self.config.get('timeout_seconds', 120)
    
    def run_linter(
        self,
        language: str,
        linter: Optional[str] = None,
        changed_files: Optional[List[str]] = None,
        baseline_issues: Optional[List[LintIssue]] = None
    ) -> LintResult:
        """
        Run linter with change-aware checking.
        
        Args:
            language: Programming language
            linter: Specific linter (auto-detect if None)
            changed_files: Only lint these files (Change-Aware)
            baseline_issues: Previous issues to filter out (show only new)
        """
        start_time = __import__('datetime').datetime.now()
        
        # Detect linter if not specified
        if not linter:
            linter = self._detect_linter(language)
        
        # Determine files to check
        if changed_files:
            files_to_check = [str(self.project_path / f) for f in changed_files]
            changed_files_only = True
        else:
            files_to_check = None
            changed_files_only = False
        
        # Run linter
        if language == 'python':
            issues = self._run_python_linter(linter, files_to_check)
        elif language == 'java':
            issues = self._run_java_linter(linter, files_to_check)
        elif language in ['javascript', 'typescript']:
            issues = self._run_js_linter(linter, files_to_check)
        else:
            issues = []
        
        # Filter for new issues only if baseline provided
        if baseline_issues:
            issues = self._filter_new_issues(issues, baseline_issues)
            new_issues_only = True
        else:
            new_issues_only = False
        
        # Count by severity
        errors = sum(1 for i in issues if i.severity == IssueSeverity.ERROR)
        warnings = sum(1 for i in issues if i.severity == IssueSeverity.WARNING)
        info = sum(1 for i in issues if i.severity == IssueSeverity.INFO)
        
        # Determine pass/fail
        passed = True
        if self.fail_on_error and errors > self.max_errors:
            passed = False
        if warnings > self.max_warnings:
            passed = False
        
        duration = (__import__('datetime').datetime.now() - start_time).total_seconds()
        
        return LintResult(
            passed=passed,
            linter=linter,
            files_checked=len(files_to_check) if files_to_check else 0,
            total_issues=len(issues),
            errors=errors,
            warnings=warnings,
            info=info,
            issues=issues,
            changed_files_only=changed_files_only,
            new_issues_only=new_issues_only,
            duration_seconds=duration
        )
    
    def _detect_linter(self, language: str) -> str:
        """Auto-detect appropriate linter"""
        if language == 'python':
            if self._is_tool_available('flake8'):
                return 'flake8'
            elif self._is_tool_available('pylint'):
                return 'pylint'
            return 'flake8'
        elif language == 'java':
            return 'checkstyle'
        elif language in ['javascript', 'typescript']:
            return 'eslint'
        return 'unknown'
    
    def _is_tool_available(self, tool: str) -> bool:
        """Check if a tool is available"""
        try:
            subprocess.run(
                [tool, '--version'],
                capture_output=True,
                timeout=5
            )
            return True
        except:
            return False
    
    def _run_python_linter(
        self,
        linter: str,
        files: Optional[List[str]]
    ) -> List[LintIssue]:
        """Run Python linter (flake8, pylint, etc.)"""
        issues = []
        
        if linter == 'flake8':
            cmd = ['flake8', '--format=json']
            if files:
                cmd.extend(files)
            else:
                cmd.append(str(self.project_path))
            
            try:
                result = subprocess.run(
                    cmd,
                    cwd=self.project_path,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout
                )
                
                issues = self._parse_flake8_output(result.stdout)
            except:
                pass
        
        elif linter == 'pylint':
            cmd = ['pylint', '--output-format=json']
            if files:
                cmd.extend(files)
            else:
                cmd.append(str(self.project_path))
            
            try:
                result = subprocess.run(
                    cmd,
                    cwd=self.project_path,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout
                )
                
                issues = self._parse_pylint_output(result.stdout)
            except:
                pass
        
        return issues
    
    def _run_java_linter(
        self,
        linter: str,
        files: Optional[List[str]]
    ) -> List[LintIssue]:
        """Run Java linter (checkstyle, PMD, etc.)"""
        issues = []
        
        if linter == 'checkstyle':
            # Run via Maven or Gradle
            if (self.project_path / 'pom.xml').exists():
                cmd = ['mvn', 'checkstyle:check']
            elif (self.project_path / 'build.gradle').exists():
                cmd = ['gradle', 'checkstyle']
            else:
                return issues
            
            try:
                result = subprocess.run(
                    cmd,
                    cwd=self.project_path,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout
                )
                
                issues = self._parse_checkstyle_output(result.stdout)
            except:
                pass
        
        return issues
    
    def _run_js_linter(
        self,
        linter: str,
        files: Optional[List[str]]
    ) -> List[LintIssue]:
        """Run JavaScript/TypeScript linter (ESLint)"""
        issues = []
        
        if linter == 'eslint':
            cmd = ['npx', 'eslint', '--format=json']
            if files:
                cmd.extend(files)
            else:
                cmd.append('.')
            
            try:
                result = subprocess.run(
                    cmd,
                    cwd=self.project_path,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout
                )
                
                issues = self._parse_eslint_output(result.stdout)
            except:
                pass
        
        return issues
    
    def _parse_flake8_output(self, output: str) -> List[LintIssue]:
        """Parse flake8 JSON output"""
        issues = []
        
        # Flake8 output format varies; parse line by line
        for line in output.splitlines():
            # Format: path:line:col: CODE message
            match = re.match(r'(.+?):(\d+):(\d+):\s+([A-Z]\d+)\s+(.+)', line)
            if match:
                file_path, line_num, col, code, message = match.groups()
                
                # Determine severity from code
                severity = IssueSeverity.WARNING
                if code[0] in ['E', 'F']:  # Error
                    severity = IssueSeverity.ERROR
                elif code[0] in ['W']:  # Warning
                    severity = IssueSeverity.WARNING
                elif code[0] in ['C', 'N']:  # Convention, Naming
                    severity = IssueSeverity.INFO
                
                issues.append(LintIssue(
                    file_path=file_path,
                    line_number=int(line_num),
                    column=int(col),
                    severity=severity,
                    rule=code,
                    message=message,
                    linter='flake8'
                ))
        
        return issues
    
    def _parse_pylint_output(self, output: str) -> List[LintIssue]:
        """Parse pylint JSON output"""
        issues = []
        
        try:
            data = json.loads(output)
            for item in data:
                severity_map = {
                    'error': IssueSeverity.ERROR,
                    'warning': IssueSeverity.WARNING,
                    'convention': IssueSeverity.INFO,
                    'refactor': IssueSeverity.INFO
                }
                
                issues.append(LintIssue(
                    file_path=item['path'],
                    line_number=item['line'],
                    column=item.get('column', 0),
                    severity=severity_map.get(item['type'], IssueSeverity.WARNING),
                    rule=item['symbol'],
                    message=item['message'],
                    linter='pylint'
                ))
        except:
            pass
        
        return issues
    
    def _parse_checkstyle_output(self, output: str) -> List[LintIssue]:
        """Parse checkstyle output"""
        issues = []
        
        # Parse XML or text output
        for line in output.splitlines():
            match = re.search(r'\[ERROR\]\s+(.+?):(\d+):\s+(.+)', line)
            if match:
                file_path, line_num, message = match.groups()
                issues.append(LintIssue(
                    file_path=file_path,
                    line_number=int(line_num),
                    column=None,
                    severity=IssueSeverity.ERROR,
                    rule='checkstyle',
                    message=message,
                    linter='checkstyle'
                ))
        
        return issues
    
    def _parse_eslint_output(self, output: str) -> List[LintIssue]:
        """Parse ESLint JSON output"""
        issues = []
        
        try:
            data = json.loads(output)
            for file_result in data:
                for message in file_result.get('messages', []):
                    severity_map = {
                        2: IssueSeverity.ERROR,
                        1: IssueSeverity.WARNING,
                        0: IssueSeverity.INFO
                    }
                    
                    issues.append(LintIssue(
                        file_path=file_result['filePath'],
                        line_number=message.get('line', 0),
                        column=message.get('column'),
                        severity=severity_map.get(message.get('severity', 1), IssueSeverity.WARNING),
                        rule=message.get('ruleId', 'unknown'),
                        message=message.get('message', ''),
                        linter='eslint'
                    ))
        except:
            pass
        
        return issues
    
    def _filter_new_issues(
        self,
        current: List[LintIssue],
        baseline: List[LintIssue]
    ) -> List[LintIssue]:
        """
        Filter to show only NEW issues introduced by changes.
        Critical for Change-Aware Gates.
        """
        # Create set of baseline issue signatures
        baseline_sigs = set()
        for issue in baseline:
            sig = f"{issue.file_path}:{issue.line_number}:{issue.rule}"
            baseline_sigs.add(sig)
        
        # Filter current issues
        new_issues = []
        for issue in current:
            sig = f"{issue.file_path}:{issue.line_number}:{issue.rule}"
            if sig not in baseline_sigs:
                new_issues.append(issue)
        
        return new_issues
    
    def format_report(self, result: LintResult) -> str:
        """Format lint result as human-readable report"""
        lines = []
        lines.append("=" * 70)
        lines.append("LINTING REPORT")
        lines.append("=" * 70)
        lines.append(f"Linter: {result.linter}")
        lines.append(f"Status: {'✓ PASSED' if result.passed else '✗ FAILED'}")
        lines.append(f"Files checked: {result.files_checked}")
        lines.append(f"Changed files only: {result.changed_files_only}")
        lines.append(f"New issues only: {result.new_issues_only}")
        lines.append(f"Duration: {result.duration_seconds:.2f}s")
        lines.append("")
        lines.append(f"Total issues: {result.total_issues}")
        lines.append(f"  Errors: {result.errors}")
        lines.append(f"  Warnings: {result.warnings}")
        lines.append(f"  Info: {result.info}")
        
        if result.issues:
            lines.append("")
            lines.append("Issues:")
            lines.append("-" * 70)
            for issue in result.issues[:20]:  # Show first 20
                icon = "✗" if issue.severity == IssueSeverity.ERROR else "⚠" if issue.severity == IssueSeverity.WARNING else "ℹ"
                lines.append(f"{icon} {issue.file_path}:{issue.line_number}")
                lines.append(f"  [{issue.rule}] {issue.message}")
        
        lines.append("=" * 70)
        return "\n".join(lines)


# Example usage
if __name__ == "__main__":
    runner = LinterRunner(
        project_path="/home/user/project",
        config={
            'max_errors': 0,
            'max_warnings': 50,
            'fail_on_error': True
        }
    )
    
    # Scenario 1: Lint only changed files (Change-Aware)
    print("=== Linting Changed Files Only ===")
    changed_files = ['src/payment/service.py', 'src/auth/handler.py']
    result = runner.run_linter(
        language='python',
        changed_files=changed_files
    )
    print(runner.format_report(result))
    print()
    
    # Scenario 2: Filter for new issues only
    print("=== Showing Only New Issues ===")
    baseline_issues = []  # Would come from previous run
    result = runner.run_linter(
        language='python',
        changed_files=changed_files,
        baseline_issues=baseline_issues
    )
    print(runner.format_report(result))
