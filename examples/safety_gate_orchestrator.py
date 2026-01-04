"""
Safety Gate Orchestrator
Main coordinator integrating all safety checks with ALL 5 improvements:
1. Change-Aware Safety Gates
2. Risk-Weighted Gates
3. Security-First Gate
4. Proof of Safety Artifact
5. Deterministic Re-runs
"""

import sys
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
import json

# Import all components
sys.path.insert(0, str(Path(__file__).parent))
from test_runner import TestRunner
from linter_runner import LinterRunner
from static_analyzer import StaticAnalyzer
from build_validator import BuildValidator
from risk_scorer import RiskScorer, RiskLevel
from safety_artifact_generator import SafetyArtifactGenerator


@dataclass
class SafetyGateResult:
    """Comprehensive safety gate result"""
    # Overall status
    passed: bool
    incident_id: str
    service_name: str
    duration_seconds: float
    
    # Check results
    checks_run: List[str]
    checks_passed: List[str]
    checks_failed: List[str]
    
    # Individual results
    test_result: Optional[Dict[str, Any]]
    lint_result: Optional[Dict[str, Any]]
    analysis_result: Optional[Dict[str, Any]]
    build_result: Optional[Dict[str, Any]]
    
    # Risk assessment (Improvement #2)
    risk_assessment: Dict[str, Any]
    
    # Recommendation
    recommendation: str  # DEPLOY, CANARY, MANUAL_REVIEW
    
    # Artifact (Improvement #4)
    safety_artifact_path: Optional[str]


class SafetyGateOrchestrator:
    """
    Main safety gate coordinator with all 5 improvements.
    
    Improvements implemented:
    1. Change-Aware Gates - Only check changed files
    2. Risk-Weighted Gates - Risk-based deployment decisions
    3. Security-First Gate - Mandatory security scanning
    4. Proof of Safety Artifact - Audit trail generation
    5. Deterministic Re-runs - Reproducible builds with version locking
    """
    
    def __init__(self, project_path: str, config_path: Optional[str] = None):
        self.project_path = Path(project_path)
        
        # Load configuration with environment variable expansion
        if config_path:
            from config_loader import load_config
            self.config = load_config(config_path)
        else:
            self.config = self._default_config()
        
        # Initialize components
        self.test_runner = TestRunner(
            str(self.project_path),
            self.config.get('checks', {}).get('tests', {})
        )
        
        self.linter = LinterRunner(
            str(self.project_path),
            self.config.get('checks', {}).get('linting', {})
        )
        
        self.analyzer = StaticAnalyzer(
            str(self.project_path),
            self.config.get('checks', {}).get('static_analysis', {})
        )
        
        self.build_validator = BuildValidator(
            str(self.project_path),
            self.config.get('checks', {}).get('build', {})
        )
        
        self.risk_scorer = RiskScorer(
            self.config.get('risk_assessment', {})
        )
        
        self.artifact_generator = SafetyArtifactGenerator(
            self.config.get('artifact', {})
        )
    
    def run_all_checks(
        self,
        incident_id: str,
        service_name: str,
        language: str,
        patch_result: Dict[str, Any],
        commit_hash: str
    ) -> SafetyGateResult:
        """
        Run all safety checks with change-aware, risk-weighted approach.
        
        Args:
            incident_id: Incident identifier
            service_name: Name of service being fixed
            language: Programming language
            patch_result: Result from Step 6 (Patch Generator)
            commit_hash: Git commit hash
            
        Returns:
            SafetyGateResult with comprehensive assessment
        """
        start_time = datetime.now()
        
        checks_run = []
        checks_passed = []
        checks_failed = []
        
        # Extract changed files for Change-Aware Gates (Improvement #1)
        changed_files = [p['file_path'] for p in patch_result.get('patch_results', [])]
        
        # Check 1: Build Validation (run first - fail fast)
        print("Running build validation...")
        build_result = None
        if self._is_check_enabled('build'):
            checks_run.append('build')
            build_result = self._run_build(language)
            
            if build_result['passed']:
                checks_passed.append('build')
            else:
                checks_failed.append('build')
                # Build failure is critical - stop here
                return self._create_failed_result(
                    incident_id, service_name, start_time,
                    checks_run, checks_passed, checks_failed,
                    None, None, None, build_result,
                    patch_result, commit_hash, language,
                    "Build failed - cannot proceed"
                )
        
        # Check 2: Tests (with impact analysis - Improvement #1)
        print("Running tests (change-aware)...")
        test_result = None
        if self._is_check_enabled('tests'):
            checks_run.append('tests')
            test_result = self._run_tests(language, changed_files)
            
            if test_result['passed']:
                checks_passed.append('tests')
            else:
                checks_failed.append('tests')
        
        # Check 3: Linting (change-aware - Improvement #1)
        print("Running linting (changed files only)...")
        lint_result = None
        if self._is_check_enabled('linting'):
            checks_run.append('linting')
            lint_result = self._run_linting(language, changed_files)
            
            if lint_result['passed']:
                checks_passed.append('linting')
            else:
                checks_failed.append('linting')
        
        # Check 4: Static Analysis + Security Scan (Improvement #3)
        print("Running security-first static analysis...")
        analysis_result = None
        if self._is_check_enabled('static_analysis'):
            checks_run.append('static_analysis')
            analysis_result = self._run_analysis(language, changed_files)
            
            if analysis_result['passed']:
                checks_passed.append('static_analysis')
            else:
                checks_failed.append('static_analysis')
                # Security failures are critical
                if not analysis_result.get('security_scan_passed', True):
                    checks_failed.append('security_scan')
        
        # Calculate Risk Score (Improvement #2)
        print("Calculating risk score...")
        risk_assessment = self.risk_scorer.calculate_risk(
            service_name,
            patch_result,
            test_result,
            lint_result,
            analysis_result,
            build_result
        )
        
        # Determine overall pass/fail
        overall_passed = len(checks_failed) == 0
        
        # Get recommendation from risk assessment
        recommendation = risk_assessment.recommendation
        
        # Generate Proof of Safety Artifact (Improvement #4)
        print("Generating proof of safety artifact...")
        artifact = self.artifact_generator.generate_artifact(
            incident_id=incident_id,
            service_name=service_name,
            checks_run=checks_run,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            test_result=test_result,
            lint_result=lint_result,
            analysis_result=analysis_result,
            build_result=build_result,
            risk_assessment=asdict(risk_assessment),
            overall_passed=overall_passed,
            recommendation=recommendation,
            commit_hash=commit_hash
        )
        
        artifact_path = self.artifact_generator.save_artifact(artifact)
        
        duration = (datetime.now() - start_time).total_seconds()
        
        return SafetyGateResult(
            passed=overall_passed,
            incident_id=incident_id,
            service_name=service_name,
            duration_seconds=duration,
            checks_run=checks_run,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            test_result=test_result,
            lint_result=lint_result,
            analysis_result=analysis_result,
            build_result=build_result,
            risk_assessment=asdict(risk_assessment),
            recommendation=recommendation,
            safety_artifact_path=str(artifact_path)
        )
    
    def _run_build(self, language: str) -> Dict[str, Any]:
        """Run build validation"""
        result = self.build_validator.validate_build(language)
        return asdict(result)
    
    def _run_tests(self, language: str, changed_files: List[str]) -> Dict[str, Any]:
        """Run tests with impact analysis (Improvement #1)"""
        result = self.test_runner.run_tests(
            language=language,
            changed_files=changed_files,
            run_all=False  # Change-aware
        )
        return asdict(result)
    
    def _run_linting(self, language: str, changed_files: List[str]) -> Dict[str, Any]:
        """Run linting on changed files only (Improvement #1)"""
        result = self.linter.run_linter(
            language=language,
            changed_files=changed_files
        )
        return asdict(result)
    
    def _run_analysis(self, language: str, changed_files: List[str]) -> Dict[str, Any]:
        """Run static analysis with security scanning (Improvement #3)"""
        result = self.analyzer.analyze(
            language=language,
            changed_files=changed_files,
            security_scan=True  # Mandatory security scan
        )
        return asdict(result)
    
    def _is_check_enabled(self, check_name: str) -> bool:
        """Check if a specific check is enabled"""
        checks = self.config.get('checks', {})
        check_config = checks.get(check_name, {})
        return check_config.get('enabled', True)
    
    def _create_failed_result(
        self, incident_id, service_name, start_time,
        checks_run, checks_passed, checks_failed,
        test_result, lint_result, analysis_result, build_result,
        patch_result, commit_hash, language, error_reason
    ) -> SafetyGateResult:
        """Create a failed result (e.g., for build failures)"""
        duration = (datetime.now() - start_time).total_seconds()
        
        # Still calculate risk for audit
        risk_assessment = self.risk_scorer.calculate_risk(
            service_name,
            patch_result,
            test_result,
            lint_result,
            analysis_result,
            build_result
        )
        
        # Generate artifact
        artifact = self.artifact_generator.generate_artifact(
            incident_id=incident_id,
            service_name=service_name,
            checks_run=checks_run,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            test_result=test_result,
            lint_result=lint_result,
            analysis_result=analysis_result,
            build_result=build_result,
            risk_assessment=asdict(risk_assessment),
            overall_passed=False,
            recommendation='MANUAL_REVIEW',
            commit_hash=commit_hash
        )
        
        artifact_path = self.artifact_generator.save_artifact(artifact)
        
        return SafetyGateResult(
            passed=False,
            incident_id=incident_id,
            service_name=service_name,
            duration_seconds=duration,
            checks_run=checks_run,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            test_result=test_result,
            lint_result=lint_result,
            analysis_result=analysis_result,
            build_result=build_result,
            risk_assessment=asdict(risk_assessment),
            recommendation='MANUAL_REVIEW',
            safety_artifact_path=str(artifact_path)
        )
    
    def _default_config(self) -> Dict[str, Any]:
        """Default configuration"""
        return {
            'checks': {
                'tests': {
                    'enabled': True,
                    'required': True,
                    'minimum_coverage': 80,
                    'timeout_seconds': 300
                },
                'linting': {
                    'enabled': True,
                    'required': False,
                    'max_errors': 0,
                    'max_warnings': 50
                },
                'static_analysis': {
                    'enabled': True,
                    'required': True,
                    'fail_on_cvss': 7.0,
                    'fail_on_secrets': True
                },
                'build': {
                    'enabled': True,
                    'required': True,
                    'timeout_seconds': 600,
                    'use_containers': False
                }
            },
            'risk_assessment': {
                'low_risk_threshold': 20,
                'medium_risk_threshold': 50,
                'high_risk_threshold': 75
            }
        }
    
    def generate_report(self, result: SafetyGateResult) -> str:
        """Generate comprehensive human-readable report"""
        lines = []
        lines.append("=" * 80)
        lines.append("SAFETY GATE REPORT")
        lines.append("=" * 80)
        lines.append(f"Incident ID: {result.incident_id}")
        lines.append(f"Service: {result.service_name}")
        lines.append(f"Status: {'✓ PASSED' if result.passed else '✗ FAILED'}")
        lines.append(f"Duration: {result.duration_seconds:.2f}s")
        lines.append(f"Recommendation: {result.recommendation}")
        lines.append("")
        
        lines.append("Check Results:")
        lines.append(f"  Total checks: {len(result.checks_run)}")
        lines.append(f"  Passed: {len(result.checks_passed)}")
        lines.append(f"  Failed: {len(result.checks_failed)}")
        lines.append("")
        
        for check in result.checks_passed:
            lines.append(f"  ✓ {check}")
        for check in result.checks_failed:
            lines.append(f"  ✗ {check}")
        lines.append("")
        
        # Risk Assessment (Improvement #2)
        risk = result.risk_assessment
        lines.append("Risk Assessment:")
        lines.append(f"  Risk Level: {risk['overall_risk']}")
        lines.append(f"  Risk Score: {risk['risk_score']:.1f}/100")
        lines.append(f"  Service Criticality: {risk['service_criticality']}")
        lines.append(f"  Change Size: {risk['change_size']}")
        lines.append("")
        
        # Deployment Strategy
        lines.append("Deployment Strategy:")
        if result.recommendation == 'DEPLOY':
            lines.append("  ✓ Safe for automatic deployment")
        elif result.recommendation == 'CANARY':
            lines.append("  ⚠ Canary rollout recommended")
            lines.append("    - Deploy to 5% traffic first")
            lines.append("    - Monitor for 10 minutes")
            lines.append("    - Gradually scale to 100%")
        else:
            lines.append("  ✗ Manual review required")
            lines.append("    - Do not auto-deploy")
            lines.append("    - Requires approval")
        lines.append("")
        
        # Artifact (Improvement #4)
        lines.append("Audit Trail:")
        lines.append(f"  Artifact: {result.safety_artifact_path}")
        lines.append("  This artifact contains:")
        lines.append("    - All check results")
        lines.append("    - Tool versions (deterministic)")
        lines.append("    - Commit and build hashes")
        lines.append("    - Risk assessment")
        lines.append("    - System signature")
        lines.append("")
        
        lines.append("=" * 80)
        return "\n".join(lines)


# Example usage
if __name__ == "__main__":
    import tempfile
    import shutil
    
    # Create test project
    test_dir = Path(tempfile.mkdtemp())
    print(f"Test directory: {test_dir}")
    
    orchestrator = SafetyGateOrchestrator(
        project_path=str(test_dir)
    )
    
    # Mock patch result from Step 6
    patch_result = {
        'success': True,
        'incident_id': 'INC-001',
        'patches_applied': 2,
        'patch_results': [
            {
                'file_path': 'src/payment/service.py',
                'success': True,
                'lines_added': 15,
                'lines_removed': 8
            },
            {
                'file_path': 'src/auth/handler.py',
                'success': True,
                'lines_added': 5,
                'lines_removed': 2
            }
        ]
    }
    
    # Run all safety checks
    print("\n=== Running Safety Gates ===\n")
    result = orchestrator.run_all_checks(
        incident_id='INC-001',
        service_name='payment-service',
        language='python',
        patch_result=patch_result,
        commit_hash='abc123def456'
    )
    
    # Display report
    print(orchestrator.generate_report(result))
    
    # Cleanup
    shutil.rmtree(test_dir)
