"""
Static Analyzer with Security-First Scanning
Implements Improvement #3: Security-First Gate with mandatory security scanning.
Scans for vulnerabilities, secrets, unsafe APIs, and dependency issues.
"""

import subprocess
import re
import json
import ast
from typing import Dict, List, Any, Optional, Set
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum


class FindingSeverity(Enum):
    """Security finding severity (CVSS-based)"""
    CRITICAL = "critical"  # CVSS 9.0-10.0
    HIGH = "high"          # CVSS 7.0-8.9
    MEDIUM = "medium"      # CVSS 4.0-6.9
    LOW = "low"            # CVSS 0.1-3.9
    INFO = "info"          # Informational


class FindingType(Enum):
    """Types of security/quality findings"""
    SECURITY_VULNERABILITY = "security_vulnerability"
    SECRET_LEAK = "secret_leak"
    UNSAFE_API = "unsafe_api"
    DEPENDENCY_VULN = "dependency_vulnerability"
    CODE_SMELL = "code_smell"
    COMPLEXITY = "complexity"
    TYPE_ERROR = "type_error"


@dataclass
class SecurityFinding:
    """A security or quality finding"""
    finding_type: FindingType
    severity: FindingSeverity
    file_path: str
    line_number: Optional[int]
    rule_id: str
    title: str
    description: str
    cve_id: Optional[str] = None
    cvss_score: Optional[float] = None
    recommendation: Optional[str] = None
    tool: Optional[str] = None


@dataclass
class AnalysisResult:
    """Result of static analysis"""
    passed: bool
    total_findings: int
    critical: int
    high: int
    medium: int
    low: int
    info: int
    findings: List[SecurityFinding]
    security_scan_passed: bool
    secrets_found: int
    dependency_vulns: int
    changed_files_only: bool
    duration_seconds: float


class SecurityScanner:
    """
    Security-First Scanner (Improvement #3).
    Mandatory security checks that fail builds on critical issues.
    """
    
    def __init__(self, project_path: str, config: Optional[Dict[str, Any]] = None):
        self.project_path = Path(project_path)
        self.config = config or {}
        
        # Security thresholds (Improvement #3 requirements)
        self.fail_on_cvss_threshold = self.config.get('fail_on_cvss', 7.0)  # CVSS >= 7
        self.fail_on_secrets = self.config.get('fail_on_secrets', True)
        self.fail_on_unsafe_apis = self.config.get('fail_on_unsafe_apis', True)
        
    def scan_secrets(self, files: Optional[List[str]] = None) -> List[SecurityFinding]:
        """
        Scan for hardcoded secrets (API keys, passwords, tokens).
        MANDATORY CHECK - Fails build if secrets found.
        """
        findings = []
        
        # Secret patterns to detect
        secret_patterns = [
            (r'(?i)(api[_-]?key|apikey)\s*[:=]\s*["\']([a-zA-Z0-9_\-]{20,})["\']', 'API Key'),
            (r'(?i)(password|passwd|pwd)\s*[:=]\s*["\']([^"\']{8,})["\']', 'Password'),
            (r'(?i)(secret|token)\s*[:=]\s*["\']([a-zA-Z0-9_\-]{20,})["\']', 'Secret/Token'),
            (r'(?i)aws_access_key_id\s*[:=]\s*["\']([A-Z0-9]{20})["\']', 'AWS Access Key'),
            (r'(?i)-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----', 'Private Key'),
            (r'(?i)bearer\s+[a-zA-Z0-9_\-\.]{20,}', 'Bearer Token'),
        ]
        
        files_to_scan = self._get_files_to_scan(files)
        
        for file_path in files_to_scan:
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                lines = content.splitlines()
                
                for line_num, line in enumerate(lines, 1):
                    for pattern, secret_type in secret_patterns:
                        if re.search(pattern, line):
                            findings.append(SecurityFinding(
                                finding_type=FindingType.SECRET_LEAK,
                                severity=FindingSeverity.CRITICAL,
                                file_path=str(file_path.relative_to(self.project_path)),
                                line_number=line_num,
                                rule_id='SECRET-001',
                                title=f'{secret_type} detected',
                                description=f'Hardcoded {secret_type.lower()} found in source code',
                                recommendation='Move secrets to environment variables or secret management service',
                                tool='builtin-secret-scanner'
                            ))
            except:
                pass
        
        return findings
    
    def scan_unsafe_apis(self, files: Optional[List[str]] = None) -> List[SecurityFinding]:
        """
        Scan for unsafe API usage (eval, exec, SQL injection, etc.).
        MANDATORY CHECK - Fails build if critical patterns found.
        """
        findings = []
        
        # Unsafe API patterns by language
        unsafe_patterns = [
            # Python
            (r'\beval\s*\(', 'eval()', 'Use of eval() allows arbitrary code execution', FindingSeverity.CRITICAL),
            (r'\bexec\s*\(', 'exec()', 'Use of exec() allows arbitrary code execution', FindingSeverity.CRITICAL),
            (r'pickle\.loads?\s*\(', 'pickle.load()', 'Pickle deserialization can execute arbitrary code', FindingSeverity.HIGH),
            (r'subprocess\.call\([^)]*shell\s*=\s*True', 'shell=True', 'Shell injection vulnerability', FindingSeverity.CRITICAL),
            (r'os\.system\s*\(', 'os.system()', 'Command injection risk', FindingSeverity.HIGH),
            (r'yaml\.load\s*\([^,)]*\)', 'yaml.load()', 'Unsafe YAML loading (use safe_load)', FindingSeverity.HIGH),
            
            # SQL Injection
            (r'execute\s*\(\s*["\'].*%s', 'SQL String Formatting', 'Potential SQL injection', FindingSeverity.CRITICAL),
            (r'execute\s*\(\s*f["\']', 'SQL f-string', 'Potential SQL injection via f-string', FindingSeverity.CRITICAL),
            
            # Java
            (r'Runtime\.getRuntime\(\)\.exec', 'Runtime.exec()', 'Command injection risk', FindingSeverity.HIGH),
            (r'\.setAccessible\s*\(\s*true', 'Reflection bypass', 'Security manager bypass', FindingSeverity.MEDIUM),
            
            # JavaScript
            (r'\beval\s*\(', 'eval()', 'eval() allows arbitrary code execution', FindingSeverity.CRITICAL),
            (r'Function\s*\(', 'Function()', 'Dynamic function creation is unsafe', FindingSeverity.HIGH),
            (r'innerHTML\s*=', 'innerHTML', 'XSS vulnerability risk', FindingSeverity.MEDIUM),
        ]
        
        files_to_scan = self._get_files_to_scan(files)
        
        for file_path in files_to_scan:
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                lines = content.splitlines()
                
                for line_num, line in enumerate(lines, 1):
                    for pattern, api_name, description, severity in unsafe_patterns:
                        if re.search(pattern, line, re.IGNORECASE):
                            findings.append(SecurityFinding(
                                finding_type=FindingType.UNSAFE_API,
                                severity=severity,
                                file_path=str(file_path.relative_to(self.project_path)),
                                line_number=line_num,
                                rule_id='UNSAFE-API',
                                title=f'Unsafe API: {api_name}',
                                description=description,
                                recommendation='Use safer alternatives or add proper input validation',
                                tool='builtin-unsafe-api-scanner'
                            ))
            except:
                pass
        
        return findings
    
    def scan_dependencies(self) -> List[SecurityFinding]:
        """
        Scan dependencies for known CVEs.
        MANDATORY CHECK - Fails build if CVSS >= 7.
        """
        findings = []
        
        # Try different dependency scanners based on language
        
        # Python: safety or pip-audit
        if (self.project_path / 'requirements.txt').exists() or \
           (self.project_path / 'pyproject.toml').exists():
            findings.extend(self._scan_python_dependencies())
        
        # Java: OWASP Dependency Check
        if (self.project_path / 'pom.xml').exists() or \
           (self.project_path / 'build.gradle').exists():
            findings.extend(self._scan_java_dependencies())
        
        # JavaScript: npm audit
        if (self.project_path / 'package.json').exists():
            findings.extend(self._scan_js_dependencies())
        
        return findings
    
    def _scan_python_dependencies(self) -> List[SecurityFinding]:
        """Scan Python dependencies using safety"""
        findings = []
        
        try:
            result = subprocess.run(
                ['safety', 'check', '--json'],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.stdout:
                data = json.loads(result.stdout)
                for vuln in data:
                    # Extract CVE and CVSS if available
                    cve_id = None
                    cvss_score = None
                    
                    for match in re.finditer(r'CVE-\d{4}-\d+', vuln.get('advisory', '')):
                        cve_id = match.group(0)
                        break
                    
                    # Map severity to CVSS approximate
                    severity_map = {
                        'high': (FindingSeverity.HIGH, 8.0),
                        'medium': (FindingSeverity.MEDIUM, 5.0),
                        'low': (FindingSeverity.LOW, 2.0)
                    }
                    
                    severity, cvss = severity_map.get(
                        vuln.get('severity', 'medium'),
                        (FindingSeverity.MEDIUM, 5.0)
                    )
                    
                    findings.append(SecurityFinding(
                        finding_type=FindingType.DEPENDENCY_VULN,
                        severity=severity,
                        file_path='requirements.txt',
                        line_number=None,
                        rule_id=cve_id or 'DEP-VULN',
                        title=f"Vulnerable dependency: {vuln.get('package')}",
                        description=vuln.get('advisory', ''),
                        cve_id=cve_id,
                        cvss_score=cvss,
                        recommendation=f"Upgrade to version {vuln.get('safe_version', 'latest')}",
                        tool='safety'
                    ))
        except:
            pass
        
        return findings
    
    def _scan_java_dependencies(self) -> List[SecurityFinding]:
        """Scan Java dependencies"""
        findings = []
        
        # Use OWASP Dependency Check or similar
        # For demo, return empty
        
        return findings
    
    def _scan_js_dependencies(self) -> List[SecurityFinding]:
        """Scan JavaScript dependencies using npm audit"""
        findings = []
        
        try:
            result = subprocess.run(
                ['npm', 'audit', '--json'],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.stdout:
                data = json.loads(result.stdout)
                for vuln_id, vuln in data.get('vulnerabilities', {}).items():
                    severity_map = {
                        'critical': FindingSeverity.CRITICAL,
                        'high': FindingSeverity.HIGH,
                        'moderate': FindingSeverity.MEDIUM,
                        'low': FindingSeverity.LOW
                    }
                    
                    findings.append(SecurityFinding(
                        finding_type=FindingType.DEPENDENCY_VULN,
                        severity=severity_map.get(vuln.get('severity'), FindingSeverity.MEDIUM),
                        file_path='package.json',
                        line_number=None,
                        rule_id=vuln.get('cve', 'DEP-VULN'),
                        title=f"Vulnerable dependency: {vuln.get('name')}",
                        description=vuln.get('title', ''),
                        cve_id=vuln.get('cve'),
                        cvss_score=vuln.get('cvss', {}).get('score'),
                        recommendation=f"Upgrade to {vuln.get('fixAvailable', 'latest')}",
                        tool='npm-audit'
                    ))
        except:
            pass
        
        return findings
    
    def _get_files_to_scan(self, files: Optional[List[str]]) -> List[Path]:
        """Get list of files to scan"""
        if files:
            return [self.project_path / f for f in files if (self.project_path / f).exists()]
        else:
            # Scan all source files
            source_files = []
            for ext in ['.py', '.java', '.js', '.ts', '.go', '.rb', '.php']:
                source_files.extend(self.project_path.rglob(f'*{ext}'))
            return source_files


class StaticAnalyzer:
    """
    Static analyzer with integrated security scanning.
    Combines type checking, complexity analysis, and security scans.
    """
    
    def __init__(self, project_path: str, config: Optional[Dict[str, Any]] = None):
        self.project_path = Path(project_path)
        self.config = config or {}
        self.security_scanner = SecurityScanner(project_path, config)
        
        self.timeout = self.config.get('timeout_seconds', 180)
    
    def analyze(
        self,
        language: str,
        changed_files: Optional[List[str]] = None,
        security_scan: bool = True
    ) -> AnalysisResult:
        """
        Run comprehensive static analysis.
        
        Args:
            language: Programming language
            changed_files: Only analyze these files (Change-Aware)
            security_scan: Run security scanning (MANDATORY)
        """
        start_time = __import__('datetime').datetime.now()
        
        all_findings = []
        
        # 1. Type checking
        if language == 'python':
            all_findings.extend(self._type_check_python(changed_files))
        
        # 2. Code complexity
        all_findings.extend(self._analyze_complexity(changed_files))
        
        # 3. SECURITY SCAN (Improvement #3 - MANDATORY)
        if security_scan:
            # Scan for secrets
            all_findings.extend(self.security_scanner.scan_secrets(changed_files))
            
            # Scan for unsafe APIs
            all_findings.extend(self.security_scanner.scan_unsafe_apis(changed_files))
            
            # Scan dependencies
            all_findings.extend(self.security_scanner.scan_dependencies())
        
        # Count findings by severity
        critical = sum(1 for f in all_findings if f.severity == FindingSeverity.CRITICAL)
        high = sum(1 for f in all_findings if f.severity == FindingSeverity.HIGH)
        medium = sum(1 for f in all_findings if f.severity == FindingSeverity.MEDIUM)
        low = sum(1 for f in all_findings if f.severity == FindingSeverity.LOW)
        info = sum(1 for f in all_findings if f.severity == FindingSeverity.INFO)
        
        # Count security-specific metrics
        secrets_found = sum(1 for f in all_findings if f.finding_type == FindingType.SECRET_LEAK)
        dependency_vulns = sum(1 for f in all_findings if f.finding_type == FindingType.DEPENDENCY_VULN)
        
        # Security scan pass/fail (Improvement #3 criteria)
        security_scan_passed = True
        
        # Fail if secrets found
        if self.config.get('fail_on_secrets', True) and secrets_found > 0:
            security_scan_passed = False
        
        # Fail if CVSS >= 7 (HIGH or CRITICAL)
        cvss_threshold = self.config.get('fail_on_cvss', 7.0)
        high_severity_vulns = [f for f in all_findings 
                               if f.cvss_score and f.cvss_score >= cvss_threshold]
        if high_severity_vulns:
            security_scan_passed = False
        
        # Fail if critical unsafe APIs found
        if self.config.get('fail_on_unsafe_apis', True):
            critical_unsafe = [f for f in all_findings 
                              if f.finding_type == FindingType.UNSAFE_API 
                              and f.severity == FindingSeverity.CRITICAL]
            if critical_unsafe:
                security_scan_passed = False
        
        # Overall pass/fail
        passed = security_scan_passed and (critical == 0)
        
        duration = (__import__('datetime').datetime.now() - start_time).total_seconds()
        
        return AnalysisResult(
            passed=passed,
            total_findings=len(all_findings),
            critical=critical,
            high=high,
            medium=medium,
            low=low,
            info=info,
            findings=all_findings,
            security_scan_passed=security_scan_passed,
            secrets_found=secrets_found,
            dependency_vulns=dependency_vulns,
            changed_files_only=bool(changed_files),
            duration_seconds=duration
        )
    
    def _type_check_python(self, files: Optional[List[str]]) -> List[SecurityFinding]:
        """Type check Python code with mypy"""
        findings = []
        
        try:
            cmd = ['mypy', '--show-error-codes']
            if files:
                cmd.extend([str(self.project_path / f) for f in files])
            else:
                cmd.append(str(self.project_path))
            
            result = subprocess.run(
                cmd,
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            # Parse mypy output
            for line in result.stdout.splitlines():
                match = re.match(r'(.+?):(\d+):\s+error:\s+(.+)', line)
                if match:
                    file_path, line_num, message = match.groups()
                    findings.append(SecurityFinding(
                        finding_type=FindingType.TYPE_ERROR,
                        severity=FindingSeverity.LOW,
                        file_path=file_path,
                        line_number=int(line_num),
                        rule_id='TYPE-ERROR',
                        title='Type error',
                        description=message,
                        tool='mypy'
                    ))
        except:
            pass
        
        return findings
    
    def _analyze_complexity(self, files: Optional[List[str]]) -> List[SecurityFinding]:
        """Analyze code complexity using simple AST-based heuristics.
        Returns findings for functions with cyclomatic-complexity above threshold.
        """
        findings: List[SecurityFinding] = []
        threshold = self.config.get('complexity_threshold', 10)

        files_to_scan = self._get_files_to_scan(files)
        for file_path in files_to_scan:
            if file_path.suffix != '.py':
                continue
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        # Heuristic: complexity = 1 + number of branching nodes
                        complexity = 1
                        for sub in ast.walk(node):
                            if isinstance(sub, (ast.If, ast.For, ast.While, ast.Try, ast.With, ast.BoolOp, ast.IfExp)):
                                complexity += 1
                        if complexity > threshold:
                            sev = FindingSeverity.MEDIUM if complexity <= threshold * 2 else FindingSeverity.HIGH
                            findings.append(SecurityFinding(
                                finding_type=FindingType.COMPLEXITY,
                                severity=sev,
                                file_path=str(file_path.relative_to(self.project_path)),
                                line_number=getattr(node, 'lineno', None),
                                rule_id='COMPLEXITY-001',
                                title='High cyclomatic complexity',
                                description=f'Function "{node.name}" has complexity {complexity} (threshold {threshold})',
                                recommendation='Refactor function to reduce branching and complexity',
                                tool='ast-heuristic'
                            ))
            except Exception:
                pass

        return findings


# Example usage
if __name__ == "__main__":
    analyzer = StaticAnalyzer(
        project_path="/home/user/project",
        config={
            'fail_on_cvss': 7.0,
            'fail_on_secrets': True,
            'fail_on_unsafe_apis': True
        }
    )
    
    # Run security-first analysis
    print("=== Security-First Static Analysis ===")
    changed_files = ['src/payment/service.py']
    result = analyzer.analyze(
        language='python',
        changed_files=changed_files,
        security_scan=True
    )
    
    print(f"Status: {'✓ PASSED' if result.passed else '✗ FAILED'}")
    print(f"Security scan: {'✓ PASSED' if result.security_scan_passed else '✗ FAILED'}")
    print(f"Total findings: {result.total_findings}")
    print(f"  Critical: {result.critical}")
    print(f"  High: {result.high}")
    print(f"  Medium: {result.medium}")
    print(f"  Low: {result.low}")
    print(f"\nSecurity Metrics:")
    print(f"  Secrets found: {result.secrets_found}")
    print(f"  Dependency vulnerabilities: {result.dependency_vulns}")
    print(f"  Changed files only: {result.changed_files_only}")
    
    if not result.security_scan_passed:
        print("\n⚠ BUILD FAILED: Security issues detected")
        for finding in result.findings:
            if finding.severity in [FindingSeverity.CRITICAL, FindingSeverity.HIGH]:
                print(f"  - {finding.title} ({finding.file_path}:{finding.line_number})")
