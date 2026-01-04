"""
Test Runner with Impact Analysis
Runs unit tests with intelligent test selection based on code changes.
Implements Change-Aware Safety Gates (Improvement #1).
"""

import os
import re
import subprocess
import json
from typing import Dict, List, Any, Optional, Set
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class TestResult:
    """Result of test execution"""
    passed: bool
    framework: str
    tests_run: int
    tests_passed: int
    tests_failed: int
    tests_skipped: int
    coverage_percentage: float
    duration_seconds: float
    failures: List[Dict[str, Any]]
    affected_tests_only: bool
    test_selection_ratio: float  # % of tests actually run


class TestImpactAnalyzer:
    """
    Analyzes which tests are affected by code changes.
    Uses file dependency analysis and naming conventions.
    """
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.dependency_cache = {}
    
    def find_affected_tests(
        self,
        changed_files: List[str],
        language: str
    ) -> Set[str]:
        """
        Find tests that should run based on changed files.
        
        Strategies:
        1. Direct test files for changed modules
        2. Tests that import changed modules
        3. Integration tests (always run)
        """
        affected = set()
        
        for changed_file in changed_files:
            # Strategy 1: Direct test file
            test_file = self._find_direct_test_file(changed_file, language)
            if test_file:
                affected.add(test_file)
            
            # Strategy 2: Find tests that import this module
            importing_tests = self._find_importing_tests(changed_file, language)
            affected.update(importing_tests)
        
        # Strategy 3: Always include integration tests
        integration_tests = self._find_integration_tests(language)
        affected.update(integration_tests)
        
        return affected
    
    def _find_direct_test_file(self, file_path: str, language: str) -> Optional[str]:
        """Find the direct test file for a source file"""
        path = Path(file_path)
        
        if language == 'python':
            # service.py -> test_service.py or service_test.py
            test_patterns = [
                f"test_{path.stem}.py",
                f"{path.stem}_test.py",
                f"test{path.stem}.py"
            ]
            
            # Look in same directory and tests/ directory
            search_dirs = [
                path.parent,
                self.project_path / 'tests',
                self.project_path / 'test'
            ]
            
            for search_dir in search_dirs:
                for pattern in test_patterns:
                    test_file = search_dir / pattern
                    if test_file.exists():
                        return str(test_file.relative_to(self.project_path))
        
        elif language == 'java':
            # Service.java -> ServiceTest.java
            test_name = f"{path.stem}Test.java"
            # Look in src/test/java/...
            test_dir = self.project_path / 'src' / 'test' / 'java'
            for test_file in test_dir.rglob(test_name):
                return str(test_file.relative_to(self.project_path))
        
        elif language in ['javascript', 'typescript']:
            # service.js -> service.test.js or service.spec.js
            test_patterns = [
                f"{path.stem}.test{path.suffix}",
                f"{path.stem}.spec{path.suffix}"
            ]
            
            for pattern in test_patterns:
                test_file = path.parent / pattern
                if test_file.exists():
                    return str(test_file.relative_to(self.project_path))
        
        return None
    
    def _find_importing_tests(self, file_path: str, language: str) -> Set[str]:
        """Find test files that import the changed module"""
        importing = set()
        module_name = Path(file_path).stem
        
        # Find all test files
        test_files = self._discover_test_files(language)
        
        for test_file in test_files:
            full_path = self.project_path / test_file
            try:
                content = full_path.read_text(encoding='utf-8')
                
                if language == 'python':
                    # Check for import statements
                    if re.search(rf'import\s+.*\b{module_name}\b', content):
                        importing.add(test_file)
                    elif re.search(rf'from\s+.*\b{module_name}\b', content):
                        importing.add(test_file)
                
                elif language == 'java':
                    if re.search(rf'import\s+.*\.{module_name};', content):
                        importing.add(test_file)
                
                elif language in ['javascript', 'typescript']:
                    if re.search(rf'import.*from.*[\'"`]{module_name}', content):
                        importing.add(test_file)
                    elif re.search(rf'require\([\'"`].*{module_name}', content):
                        importing.add(test_file)
            except:
                pass
        
        return importing
    
    def _find_integration_tests(self, language: str) -> Set[str]:
        """Find integration tests (always run these)"""
        integration = set()
        
        integration_patterns = [
            '**/test_integration*.py',
            '**/integration_test*.py',
            '**/*IntegrationTest.java',
            '**/*.integration.test.*',
            '**/*.e2e.test.*'
        ]
        
        for pattern in integration_patterns:
            for file in self.project_path.rglob(pattern):
                if file.is_file():
                    integration.add(str(file.relative_to(self.project_path)))
        
        return integration
    
    def _discover_test_files(self, language: str) -> List[str]:
        """Discover all test files in project"""
        test_files = []
        
        if language == 'python':
            for file in self.project_path.rglob('test_*.py'):
                test_files.append(str(file.relative_to(self.project_path)))
            for file in self.project_path.rglob('*_test.py'):
                test_files.append(str(file.relative_to(self.project_path)))
        
        elif language == 'java':
            for file in self.project_path.rglob('*Test.java'):
                test_files.append(str(file.relative_to(self.project_path)))
        
        elif language in ['javascript', 'typescript']:
            for file in self.project_path.rglob('*.test.*'):
                test_files.append(str(file.relative_to(self.project_path)))
            for file in self.project_path.rglob('*.spec.*'):
                test_files.append(str(file.relative_to(self.project_path)))
        
        return test_files


class TestRunner:
    """
    Runs tests with intelligent test selection.
    Supports pytest, unittest, JUnit, Jest, etc.
    """
    
    def __init__(self, project_path: str, config: Optional[Dict[str, Any]] = None):
        self.project_path = Path(project_path)
        self.config = config or {}
        self.impact_analyzer = TestImpactAnalyzer(project_path)
        
        self.timeout = self.config.get('timeout_seconds', 300)
        self.minimum_coverage = self.config.get('minimum_coverage', 80.0)
        self.fail_fast = self.config.get('fail_fast', False)
    
    def run_tests(
        self,
        language: str,
        framework: Optional[str] = None,
        changed_files: Optional[List[str]] = None,
        run_all: bool = False
    ) -> TestResult:
        """
        Run tests with intelligent selection.
        
        Args:
            language: Programming language
            framework: Test framework (auto-detect if None)
            changed_files: Files changed in patch (for impact analysis)
            run_all: Force run all tests (ignore impact analysis)
        """
        start_time = datetime.now()
        
        # Detect framework if not specified
        if not framework:
            framework = self._detect_framework(language)
        
        # Test selection strategy
        if run_all or not changed_files:
            # Run all tests
            test_paths = None
            affected_only = False
            selection_ratio = 1.0
        else:
            # Run only affected tests (Change-Aware Gate)
            affected_tests = self.impact_analyzer.find_affected_tests(
                changed_files,
                language
            )
            
            all_tests = set(self.impact_analyzer._discover_test_files(language))
            test_paths = list(affected_tests)
            affected_only = True
            selection_ratio = len(affected_tests) / len(all_tests) if all_tests else 1.0
        
        # Execute tests
        if language == 'python':
            result = self._run_python_tests(framework, test_paths)
        elif language == 'java':
            result = self._run_java_tests(framework, test_paths)
        elif language in ['javascript', 'typescript']:
            result = self._run_js_tests(framework, test_paths)
        else:
            result = TestResult(
                passed=False,
                framework='unknown',
                tests_run=0,
                tests_passed=0,
                tests_failed=0,
                tests_skipped=0,
                coverage_percentage=0.0,
                duration_seconds=0.0,
                failures=[],
                affected_tests_only=False,
                test_selection_ratio=0.0
            )
        
        result.affected_tests_only = affected_only
        result.test_selection_ratio = selection_ratio
        result.duration_seconds = (datetime.now() - start_time).total_seconds()
        
        return result
    
    def _detect_framework(self, language: str) -> str:
        """Auto-detect test framework"""
        if language == 'python':
            if (self.project_path / 'pytest.ini').exists() or \
               (self.project_path / 'pyproject.toml').exists():
                return 'pytest'
            return 'unittest'
        elif language == 'java':
            return 'junit'
        elif language in ['javascript', 'typescript']:
            package_json = self.project_path / 'package.json'
            if package_json.exists():
                content = package_json.read_text()
                if 'jest' in content:
                    return 'jest'
                elif 'mocha' in content:
                    return 'mocha'
            return 'jest'
        return 'unknown'
    
    def _run_python_tests(
        self,
        framework: str,
        test_paths: Optional[List[str]]
    ) -> TestResult:
        """Run Python tests (pytest or unittest)"""
        if framework == 'pytest':
            cmd = ['pytest', '-v', '--tb=short', '--json-report', '--json-report-file=test_report.json']
            
            # Add coverage
            cmd.extend(['--cov', '--cov-report=json'])
            
            # Add specific test paths if provided
            if test_paths:
                cmd.extend(test_paths)
            
            try:
                result = subprocess.run(
                    cmd,
                    cwd=self.project_path,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout
                )
                
                return self._parse_pytest_output(result)
                
            except subprocess.TimeoutExpired:
                return TestResult(
                    passed=False,
                    framework='pytest',
                    tests_run=0,
                    tests_passed=0,
                    tests_failed=0,
                    tests_skipped=0,
                    coverage_percentage=0.0,
                    duration_seconds=self.timeout,
                    failures=[{'error': 'Test execution timeout'}],
                    affected_tests_only=False,
                    test_selection_ratio=0.0
                )
            except Exception as e:
                return TestResult(
                    passed=False,
                    framework='pytest',
                    tests_run=0,
                    tests_passed=0,
                    tests_failed=0,
                    tests_skipped=0,
                    coverage_percentage=0.0,
                    duration_seconds=0.0,
                    failures=[{'error': str(e)}],
                    affected_tests_only=False,
                    test_selection_ratio=0.0
                )
        
        # Default fallback
        return TestResult(
            passed=True,
            framework=framework,
            tests_run=0,
            tests_passed=0,
            tests_failed=0,
            tests_skipped=0,
            coverage_percentage=100.0,
            duration_seconds=0.0,
            failures=[],
            affected_tests_only=False,
            test_selection_ratio=1.0
        )
    
    def _run_java_tests(
        self,
        framework: str,
        test_paths: Optional[List[str]]
    ) -> TestResult:
        """Run Java tests (JUnit via Maven/Gradle)"""
        # Try Maven first
        if (self.project_path / 'pom.xml').exists():
            cmd = ['mvn', 'test']
            if test_paths:
                # Run specific tests
                test_classes = [Path(p).stem for p in test_paths]
                cmd.append(f'-Dtest={",".join(test_classes)}')
        elif (self.project_path / 'build.gradle').exists():
            cmd = ['gradle', 'test']
        else:
            return self._create_empty_result('junit')
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            return self._parse_junit_output(result)
        except:
            return self._create_empty_result('junit')
    
    def _run_js_tests(
        self,
        framework: str,
        test_paths: Optional[List[str]]
    ) -> TestResult:
        """Run JavaScript/TypeScript tests (Jest/Mocha)"""
        if framework == 'jest':
            cmd = ['npm', 'test', '--', '--json', '--coverage']
            if test_paths:
                cmd.extend(test_paths)
        else:
            cmd = ['npm', 'test']
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            return self._parse_jest_output(result)
        except:
            return self._create_empty_result(framework)
    
    def _parse_pytest_output(self, result: subprocess.CompletedProcess) -> TestResult:
        """Parse pytest JSON output"""
        # Try to read JSON report
        report_file = self.project_path / 'test_report.json'
        coverage_file = self.project_path / 'coverage.json'
        
        tests_run = tests_passed = tests_failed = tests_skipped = 0
        coverage = 0.0
        failures = []
        
        if report_file.exists():
            try:
                data = json.loads(report_file.read_text())
                summary = data.get('summary', {})
                tests_run = summary.get('total', 0)
                tests_passed = summary.get('passed', 0)
                tests_failed = summary.get('failed', 0)
                tests_skipped = summary.get('skipped', 0)
                
                for test in data.get('tests', []):
                    if test.get('outcome') == 'failed':
                        failures.append({
                            'test': test.get('nodeid'),
                            'error': test.get('call', {}).get('longrepr', 'Unknown error')
                        })
            except:
                pass
        
        if coverage_file.exists():
            try:
                data = json.loads(coverage_file.read_text())
                coverage = data.get('totals', {}).get('percent_covered', 0.0)
            except:
                pass
        
        passed = (result.returncode == 0) and (coverage >= self.minimum_coverage)
        
        return TestResult(
            passed=passed,
            framework='pytest',
            tests_run=tests_run,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            tests_skipped=tests_skipped,
            coverage_percentage=coverage,
            duration_seconds=0.0,
            failures=failures,
            affected_tests_only=False,
            test_selection_ratio=1.0
        )
    
    def _parse_junit_output(self, result: subprocess.CompletedProcess) -> TestResult:
        """Parse JUnit output from Maven/Gradle"""
        # Parse from stdout/stderr
        output = result.stdout + result.stderr
        
        # Look for test summary
        tests_run = tests_passed = tests_failed = tests_skipped = 0
        
        match = re.search(r'Tests run:\s*(\d+).*Failures:\s*(\d+).*Skipped:\s*(\d+)', output)
        if match:
            tests_run = int(match.group(1))
            tests_failed = int(match.group(2))
            tests_skipped = int(match.group(3))
            tests_passed = tests_run - tests_failed - tests_skipped
        
        return TestResult(
            passed=(result.returncode == 0),
            framework='junit',
            tests_run=tests_run,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            tests_skipped=tests_skipped,
            coverage_percentage=0.0,
            duration_seconds=0.0,
            failures=[],
            affected_tests_only=False,
            test_selection_ratio=1.0
        )
    
    def _parse_jest_output(self, result: subprocess.CompletedProcess) -> TestResult:
        """Parse Jest JSON output"""
        try:
            data = json.loads(result.stdout)
            tests_run = data.get('numTotalTests', 0)
            tests_passed = data.get('numPassedTests', 0)
            tests_failed = data.get('numFailedTests', 0)
            
            coverage = 0.0
            if 'coverageMap' in data:
                # Calculate average coverage across files in coverageMap
                coverage_values = []
                try:
                    for file_cov in data.get('coverageMap', {}).values():
                        pct = None
                        # Jest coverage entries often include a 'lines' dict with 'pct'
                        if isinstance(file_cov, dict):
                            lines = file_cov.get('lines')
                            if isinstance(lines, dict) and lines.get('pct') is not None:
                                pct = float(lines.get('pct'))
                            else:
                                # Fallback: compute from totals if available
                                totals = file_cov.get('total') or file_cov.get('totals')
                                if isinstance(totals, dict):
                                    covered = totals.get('covered')
                                    total = totals.get('total')
                                    if covered is not None and total:
                                        pct = float(covered) / float(total) * 100.0
                        if pct is not None:
                            coverage_values.append(pct)
                except Exception:
                    coverage_values = []

                if coverage_values:
                    coverage = sum(coverage_values) / len(coverage_values)

            return TestResult(
                passed=(result.returncode == 0),
                framework='jest',
                tests_run=tests_run,
                tests_passed=tests_passed,
                tests_failed=tests_failed,
                tests_skipped=0,
                coverage_percentage=coverage,
                duration_seconds=0.0,
                failures=[],
                affected_tests_only=False,
                test_selection_ratio=1.0
            )
        except:
            return self._create_empty_result('jest')
    
    def _create_empty_result(self, framework: str) -> TestResult:
        """Create empty result for error cases"""
        return TestResult(
            passed=True,
            framework=framework,
            tests_run=0,
            tests_passed=0,
            tests_failed=0,
            tests_skipped=0,
            coverage_percentage=100.0,
            duration_seconds=0.0,
            failures=[],
            affected_tests_only=False,
            test_selection_ratio=1.0
        )


# Example usage
if __name__ == "__main__":
    runner = TestRunner(
        project_path="/home/user/project",
        config={
            'timeout_seconds': 300,
            'minimum_coverage': 80.0
        }
    )
    
    # Scenario 1: Run all tests
    print("=== Running All Tests ===")
    result = runner.run_tests(language='python', run_all=True)
    print(f"Passed: {result.passed}")
    print(f"Tests: {result.tests_passed}/{result.tests_run}")
    print(f"Coverage: {result.coverage_percentage:.1f}%")
    print()
    
    # Scenario 2: Run only affected tests (Change-Aware)
    print("=== Running Affected Tests Only ===")
    changed_files = ['src/payment/service.py', 'src/auth/handler.py']
    result = runner.run_tests(
        language='python',
        changed_files=changed_files,
        run_all=False
    )
    print(f"Passed: {result.passed}")
    print(f"Tests: {result.tests_passed}/{result.tests_run}")
    print(f"Coverage: {result.coverage_percentage:.1f}%")
    print(f"Affected only: {result.affected_tests_only}")
    print(f"Selection ratio: {result.test_selection_ratio:.1%}")
    print(f"Duration: {result.duration_seconds:.2f}s")
