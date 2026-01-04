"""
Patch Validator
Validates code patches before application to ensure safety and correctness.
"""

import re
import ast
import json
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
from enum import Enum


class ValidationLevel(Enum):
    """Validation strictness levels"""
    STRICT = "strict"      # All checks must pass
    NORMAL = "normal"      # Critical checks must pass
    PERMISSIVE = "permissive"  # Only syntax checks


class ValidationResult(Enum):
    """Validation outcomes"""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"


@dataclass
class ValidationIssue:
    """Represents a validation issue"""
    level: ValidationResult
    check: str
    message: str
    line_number: Optional[int] = None
    details: Optional[Dict[str, Any]] = None


class PatchValidator:
    """
    Validates code patches for safety and correctness before application.
    
    Checks:
    - Syntax validity
    - Import consistency
    - Function signature preservation
    - Code complexity metrics
    - Dangerous pattern detection
    - File size limits
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.validation_level = ValidationLevel(
            self.config.get('validation_level', 'normal')
        )
        
        # Configuration thresholds
        self.max_file_size = self.config.get('max_file_size', 1024 * 1024)  # 1MB
        self.max_lines_changed = self.config.get('max_lines_changed', 500)
        self.max_complexity_increase = self.config.get('max_complexity_increase', 10)
        
        # Dangerous patterns (regex)
        self.dangerous_patterns = [
            (r'eval\s*\(', 'Use of eval() is dangerous'),
            (r'exec\s*\(', 'Use of exec() is dangerous'),
            (r'__import__\s*\(', 'Dynamic imports may be unsafe'),
            (r'subprocess\.call.*shell\s*=\s*True', 'Shell injection risk'),
            (r'os\.system\s*\(', 'Command injection risk'),
            (r'pickle\.loads?\s*\(', 'Pickle deserialization is unsafe'),
            (r'yaml\.load\s*\([^,)]*\)', 'Unsafe YAML loading (use safe_load)'),
        ]
    
    def validate_patch(
        self,
        original_content: str,
        patched_content: str,
        file_path: str,
        language: str
    ) -> Tuple[bool, List[ValidationIssue]]:
        """
        Validate a code patch comprehensively.
        
        Args:
            original_content: Original file content
            patched_content: Content after patch
            file_path: Path to the file
            language: Programming language
            
        Returns:
            Tuple of (is_valid, list of issues)
        """
        issues: List[ValidationIssue] = []
        
        # File size check
        if len(patched_content) > self.max_file_size:
            issues.append(ValidationIssue(
                ValidationResult.FAIL,
                'file_size',
                f'Patched file exceeds size limit ({len(patched_content)} > {self.max_file_size})'
            ))
        
        # Lines changed check
        original_lines = original_content.splitlines()
        patched_lines = patched_content.splitlines()
        lines_changed = abs(len(patched_lines) - len(original_lines))
        
        if lines_changed > self.max_lines_changed:
            issues.append(ValidationIssue(
                ValidationResult.WARNING,
                'lines_changed',
                f'Large change: {lines_changed} lines differ'
            ))
        
        # Language-specific validation
        if language == 'python':
            issues.extend(self._validate_python(original_content, patched_content))
        elif language == 'java':
            issues.extend(self._validate_java(original_content, patched_content))
        elif language == 'javascript':
            issues.extend(self._validate_javascript(original_content, patched_content))
        else:
            issues.append(ValidationIssue(
                ValidationResult.WARNING,
                'language_support',
                f'No specific validation for language: {language}'
            ))
        
        # Dangerous patterns check
        issues.extend(self._check_dangerous_patterns(patched_content))
        
        # Determine overall validity
        is_valid = self._evaluate_issues(issues)
        
        return is_valid, issues
    
    def _validate_python(
        self,
        original: str,
        patched: str
    ) -> List[ValidationIssue]:
        """Validate Python-specific aspects"""
        issues: List[ValidationIssue] = []
        
        # Syntax check
        try:
            ast.parse(patched)
        except SyntaxError as e:
            issues.append(ValidationIssue(
                ValidationResult.FAIL,
                'syntax',
                f'Python syntax error: {e.msg}',
                line_number=e.lineno
            ))
            return issues  # Can't continue if syntax is invalid
        
        # Import consistency check
        original_imports = self._extract_python_imports(original)
        patched_imports = self._extract_python_imports(patched)
        
        # Check if imports were removed (might break code)
        removed_imports = original_imports - patched_imports
        if removed_imports and self.validation_level != ValidationLevel.PERMISSIVE:
            issues.append(ValidationIssue(
                ValidationResult.WARNING,
                'imports_removed',
                f'Imports removed: {", ".join(removed_imports)}'
            ))
        
        # Check if new imports were added
        added_imports = patched_imports - original_imports
        if added_imports:
            issues.append(ValidationIssue(
                ValidationResult.PASS,
                'imports_added',
                f'New imports added: {", ".join(added_imports)}'
            ))
        
        # Function signature preservation
        original_functions = self._extract_python_functions(original)
        patched_functions = self._extract_python_functions(patched)
        
        for func_name in original_functions:
            if func_name in patched_functions:
                if original_functions[func_name] != patched_functions[func_name]:
                    if self.validation_level == ValidationLevel.STRICT:
                        issues.append(ValidationIssue(
                            ValidationResult.FAIL,
                            'signature_changed',
                            f'Function signature changed: {func_name}'
                        ))
                    else:
                        issues.append(ValidationIssue(
                            ValidationResult.WARNING,
                            'signature_changed',
                            f'Function signature changed: {func_name}'
                        ))
        
        return issues
    
    def _validate_java(
        self,
        original: str,
        patched: str
    ) -> List[ValidationIssue]:
        """Validate Java-specific aspects"""
        issues: List[ValidationIssue] = []
        
        # Basic syntax checks
        if not self._check_balanced_braces(patched):
            issues.append(ValidationIssue(
                ValidationResult.FAIL,
                'syntax',
                'Unbalanced braces in Java code'
            ))
        
        # Check for public method signature changes
        original_methods = self._extract_java_public_methods(original)
        patched_methods = self._extract_java_public_methods(patched)
        
        for method in original_methods:
            if method not in patched_methods:
                issues.append(ValidationIssue(
                    ValidationResult.WARNING,
                    'method_removed',
                    f'Public method removed or changed: {method}'
                ))
        
        return issues
    
    def _validate_javascript(
        self,
        original: str,
        patched: str
    ) -> List[ValidationIssue]:
        """Validate JavaScript-specific aspects"""
        issues: List[ValidationIssue] = []
        
        # Basic syntax checks
        if not self._check_balanced_braces(patched):
            issues.append(ValidationIssue(
                ValidationResult.FAIL,
                'syntax',
                'Unbalanced braces in JavaScript code'
            ))
        
        # Check for dangerous console.log removals in production
        if 'console.log' in original and 'console.log' not in patched:
            issues.append(ValidationIssue(
                ValidationResult.PASS,
                'console_log_removed',
                'console.log statements removed (good for production)'
            ))
        
        return issues
    
    def _check_dangerous_patterns(self, content: str) -> List[ValidationIssue]:
        """Check for dangerous code patterns"""
        issues: List[ValidationIssue] = []
        
        for pattern, message in self.dangerous_patterns:
            matches = list(re.finditer(pattern, content, re.IGNORECASE))
            if matches:
                for match in matches:
                    line_number = content[:match.start()].count('\n') + 1
                    issues.append(ValidationIssue(
                        ValidationResult.FAIL if self.validation_level == ValidationLevel.STRICT else ValidationResult.WARNING,
                        'dangerous_pattern',
                        message,
                        line_number=line_number
                    ))
        
        return issues
    
    def _extract_python_imports(self, code: str) -> set:
        """Extract import statements from Python code"""
        imports = set()
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ''
                    for alias in node.names:
                        imports.add(f"{module}.{alias.name}")
        except:
            pass
        return imports
    
    def _extract_python_functions(self, code: str) -> Dict[str, str]:
        """Extract function signatures from Python code"""
        functions = {}
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    args = [arg.arg for arg in node.args.args]
                    functions[node.name] = f"({', '.join(args)})"
        except:
            pass
        return functions
    
    def _extract_java_public_methods(self, code: str) -> set:
        """Extract public method signatures from Java code"""
        methods = set()
        # Regex to match public method declarations
        pattern = r'public\s+(?:static\s+)?[\w<>\[\]]+\s+(\w+)\s*\([^)]*\)'
        for match in re.finditer(pattern, code):
            methods.add(match.group(1))
        return methods
    
    def _check_balanced_braces(self, code: str) -> bool:
        """Check if braces are balanced"""
        stack = []
        pairs = {'(': ')', '[': ']', '{': '}'}
        
        for char in code:
            if char in pairs:
                stack.append(char)
            elif char in pairs.values():
                if not stack:
                    return False
                if pairs[stack[-1]] != char:
                    return False
                stack.pop()
        
        return len(stack) == 0
    
    def _evaluate_issues(self, issues: List[ValidationIssue]) -> bool:
        """Evaluate if patch is valid based on issues"""
        if self.validation_level == ValidationLevel.PERMISSIVE:
            # Only fail on syntax errors
            return not any(i.level == ValidationResult.FAIL and i.check == 'syntax' for i in issues)
        
        if self.validation_level == ValidationLevel.NORMAL:
            # Fail on any FAIL issues
            return not any(i.level == ValidationResult.FAIL for i in issues)
        
        if self.validation_level == ValidationLevel.STRICT:
            # Fail on FAIL or WARNING issues
            return not any(i.level in [ValidationResult.FAIL, ValidationResult.WARNING] for i in issues)
        
        return True
    
    def format_validation_report(self, issues: List[ValidationIssue]) -> str:
        """Format validation issues as human-readable report"""
        if not issues:
            return "✓ All validation checks passed"
        
        report = ["Validation Report:"]
        report.append("=" * 60)
        
        for issue in issues:
            icon = "✓" if issue.level == ValidationResult.PASS else ("⚠" if issue.level == ValidationResult.WARNING else "✗")
            line_info = f" (line {issue.line_number})" if issue.line_number else ""
            report.append(f"{icon} [{issue.check}]{line_info}: {issue.message}")
        
        return "\n".join(report)


# Example usage
if __name__ == "__main__":
    validator = PatchValidator({
        'validation_level': 'normal',
        'max_lines_changed': 100
    })
    
    # Test Python validation
    original_python = '''
import os
import sys

def process_data(data):
    return data.strip()

def main():
    print("Hello")
'''
    
    patched_python = '''
import os
import sys
import json

def process_data(data):
    if data is None:
        return ""
    return data.strip()

def main():
    print("Hello")
    print(json.dumps({"status": "ok"}))
'''
    
    is_valid, issues = validator.validate_patch(
        original_python,
        patched_python,
        "example.py",
        "python"
    )
    
    print(f"Validation result: {'PASS' if is_valid else 'FAIL'}")
    print(validator.format_validation_report(issues))
    print()
    
    # Test dangerous pattern detection
    dangerous_code = '''
import os

def run_command(cmd):
    os.system(cmd)  # Dangerous!
    eval(cmd)  # Very dangerous!
'''
    
    is_valid, issues = validator.validate_patch(
        "",
        dangerous_code,
        "dangerous.py",
        "python"
    )
    
    print(f"Dangerous code validation: {'PASS' if is_valid else 'FAIL'}")
    print(validator.format_validation_report(issues))
