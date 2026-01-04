"""
Risk Scorer for Weighted Gates
Implements Improvement #2: Risk-Weighted Gates (Not All Failures Are Equal).
Calculates risk = ServiceCriticality × ChangeSize × ErrorSeverity
"""

from typing import Dict, List, Any, Optional
from enum import Enum
from dataclasses import dataclass


class RiskLevel(Enum):
    """Overall risk levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ServiceCriticality(Enum):
    """Service criticality levels"""
    CRITICAL = 5    # Payment, Auth, Core API
    HIGH = 4        # User-facing services
    MEDIUM = 3      # Background jobs, analytics
    LOW = 2         # Internal tools
    DEV = 1         # Development/test services


class ChangeSize(Enum):
    """Size of code changes"""
    TINY = 1        # 1-10 lines
    SMALL = 2       # 11-50 lines
    MEDIUM = 3      # 51-200 lines
    LARGE = 4       # 201-500 lines
    HUGE = 5        # 500+ lines


@dataclass
class RiskScore:
    """Risk assessment result"""
    overall_risk: RiskLevel
    risk_score: float  # 0-100
    service_criticality: ServiceCriticality
    change_size: ChangeSize
    error_severity: float  # 0-10
    recommendation: str  # DEPLOY, CANARY, MANUAL_REVIEW
    reasoning: str
    factors: Dict[str, Any]


class RiskScorer:
    """
    Risk-weighted gate calculator (Improvement #2).
    Uses formula: Risk = ServiceCriticality × ChangeSize × ErrorSeverity
    
    This directly connects Step 7 → Step 8 deployment strategy:
    - Low risk → Auto deploy
    - Medium risk → Canary deployment
    - High risk → Manual approval
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # Service criticality mapping
        self.service_criticality_map = self.config.get('service_criticality', {
            'payment-service': ServiceCriticality.CRITICAL,
            'auth-service': ServiceCriticality.CRITICAL,
            'api-gateway': ServiceCriticality.CRITICAL,
            'user-service': ServiceCriticality.HIGH,
            'notification-service': ServiceCriticality.MEDIUM,
            'analytics-service': ServiceCriticality.LOW
        })
        
        # Risk thresholds
        self.low_risk_threshold = self.config.get('low_risk_threshold', 20)
        self.medium_risk_threshold = self.config.get('medium_risk_threshold', 50)
        self.high_risk_threshold = self.config.get('high_risk_threshold', 75)
    
    def calculate_risk(
        self,
        service_name: str,
        patch_result: Dict[str, Any],
        test_result: Optional[Dict[str, Any]] = None,
        lint_result: Optional[Dict[str, Any]] = None,
        analysis_result: Optional[Dict[str, Any]] = None,
        build_result: Optional[Dict[str, Any]] = None
    ) -> RiskScore:
        """
        Calculate comprehensive risk score.
        
        Formula: Risk = ServiceCriticality × ChangeSize × ErrorSeverity
        
        Args:
            service_name: Name of the service
            patch_result: Result from Step 6 (Patch Generator)
            test_result: Test results
            lint_result: Linting results
            analysis_result: Static analysis results
            build_result: Build results
        
        Returns:
            RiskScore with recommendation
        """
        # Factor 1: Service Criticality (1-5)
        service_criticality = self._get_service_criticality(service_name)
        criticality_score = service_criticality.value
        
        # Factor 2: Change Size (1-5)
        change_size = self._calculate_change_size(patch_result)
        change_score = change_size.value
        
        # Factor 3: Error Severity (0-10)
        error_severity = self._calculate_error_severity(
            test_result,
            lint_result,
            analysis_result,
            build_result
        )
        
        # Calculate composite risk score (0-100)
        # Formula: (Criticality * ChangeSize * ErrorSeverity) / max_possible * 100
        max_possible = 5 * 5 * 10  # 250
        raw_score = criticality_score * change_score * error_severity
        risk_score = (raw_score / max_possible) * 100
        
        # Determine overall risk level
        if risk_score < self.low_risk_threshold:
            overall_risk = RiskLevel.LOW
        elif risk_score < self.medium_risk_threshold:
            overall_risk = RiskLevel.MEDIUM
        elif risk_score < self.high_risk_threshold:
            overall_risk = RiskLevel.HIGH
        else:
            overall_risk = RiskLevel.CRITICAL
        
        # Determine recommendation (Improvement #2)
        recommendation, reasoning = self._get_recommendation(
            overall_risk,
            service_criticality,
            test_result,
            analysis_result
        )
        
        # Collect factors for audit
        factors = {
            'service_criticality': service_criticality.name,
            'criticality_score': criticality_score,
            'change_size': change_size.name,
            'change_score': change_score,
            'error_severity': error_severity,
            'lines_changed': self._count_lines_changed(patch_result),
            'tests_failed': test_result.get('tests_failed', 0) if test_result else 0,
            'lint_errors': lint_result.get('errors', 0) if lint_result else 0,
            'security_issues': self._count_security_issues(analysis_result),
            'build_failed': not build_result.get('passed', True) if build_result else False
        }
        
        return RiskScore(
            overall_risk=overall_risk,
            risk_score=risk_score,
            service_criticality=service_criticality,
            change_size=change_size,
            error_severity=error_severity,
            recommendation=recommendation,
            reasoning=reasoning,
            factors=factors
        )
    
    def _get_service_criticality(self, service_name: str) -> ServiceCriticality:
        """Get service criticality level"""
        # Check exact match
        if service_name in self.service_criticality_map:
            return self.service_criticality_map[service_name]
        
        # Check keyword-based matching
        if any(keyword in service_name.lower() for keyword in ['payment', 'auth', 'security']):
            return ServiceCriticality.CRITICAL
        elif any(keyword in service_name.lower() for keyword in ['api', 'gateway', 'user']):
            return ServiceCriticality.HIGH
        elif any(keyword in service_name.lower() for keyword in ['notification', 'email', 'worker']):
            return ServiceCriticality.MEDIUM
        elif any(keyword in service_name.lower() for keyword in ['analytics', 'logging', 'metrics']):
            return ServiceCriticality.LOW
        
        # Default to medium
        return ServiceCriticality.MEDIUM
    
    def _calculate_change_size(self, patch_result: Dict[str, Any]) -> ChangeSize:
        """Calculate change size based on lines changed"""
        total_lines = self._count_lines_changed(patch_result)
        
        if total_lines <= 10:
            return ChangeSize.TINY
        elif total_lines <= 50:
            return ChangeSize.SMALL
        elif total_lines <= 200:
            return ChangeSize.MEDIUM
        elif total_lines <= 500:
            return ChangeSize.LARGE
        else:
            return ChangeSize.HUGE
    
    def _count_lines_changed(self, patch_result: Dict[str, Any]) -> int:
        """Count total lines changed in patches"""
        total = 0
        for patch in patch_result.get('patch_results', []):
            total += patch.get('lines_added', 0)
            total += patch.get('lines_removed', 0)
        return total
    
    def _calculate_error_severity(
        self,
        test_result: Optional[Dict[str, Any]],
        lint_result: Optional[Dict[str, Any]],
        analysis_result: Optional[Dict[str, Any]],
        build_result: Optional[Dict[str, Any]]
    ) -> float:
        """
        Calculate error severity (0-10).
        Higher score = more severe issues.
        """
        severity = 0.0
        
        # Build failures are critical (max severity)
        if build_result and not build_result.get('passed', True):
            return 10.0
        
        # Test failures
        if test_result:
            tests_failed = test_result.get('tests_failed', 0)
            tests_run = test_result.get('tests_run', 1)
            if tests_run > 0:
                failure_rate = tests_failed / tests_run
                severity += failure_rate * 4  # Up to 4 points
            
            # Coverage drop
            coverage = test_result.get('coverage_percentage', 100)
            if coverage < 80:
                severity += (80 - coverage) / 20  # Up to 4 points
        
        # Security issues (Improvement #3)
        if analysis_result:
            if not analysis_result.get('security_scan_passed', True):
                severity += 5.0  # Security failures are severe
            
            # Add severity for critical/high findings
            critical = analysis_result.get('critical', 0)
            high = analysis_result.get('high', 0)
            severity += min(critical * 0.5 + high * 0.25, 3.0)  # Up to 3 points
        
        # Lint errors
        if lint_result:
            errors = lint_result.get('errors', 0)
            severity += min(errors * 0.1, 1.0)  # Up to 1 point
        
        return min(severity, 10.0)  # Cap at 10
    
    def _count_security_issues(self, analysis_result: Optional[Dict[str, Any]]) -> int:
        """Count critical security issues"""
        if not analysis_result:
            return 0
        
        return analysis_result.get('critical', 0) + analysis_result.get('high', 0)
    
    def _get_recommendation(
        self,
        overall_risk: RiskLevel,
        service_criticality: ServiceCriticality,
        test_result: Optional[Dict[str, Any]],
        analysis_result: Optional[Dict[str, Any]]
    ) -> tuple:
        """
        Get deployment recommendation based on risk.
        Improvement #2: This connects Step 7 → Step 8
        """
        # Critical services or critical risk → Manual review
        if service_criticality == ServiceCriticality.CRITICAL and overall_risk in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            return 'MANUAL_REVIEW', 'Critical service with high risk requires manual approval'
        
        # Security failures → Manual review
        if analysis_result and not analysis_result.get('security_scan_passed', True):
            return 'MANUAL_REVIEW', 'Security scan failed - manual review required'
        
        # Test failures on critical/high services → Manual review
        if test_result and test_result.get('tests_failed', 0) > 0:
            if service_criticality in [ServiceCriticality.CRITICAL, ServiceCriticality.HIGH]:
                return 'MANUAL_REVIEW', 'Test failures on critical service require review'
        
        # Risk-based recommendations (Improvement #2)
        if overall_risk == RiskLevel.LOW:
            return 'DEPLOY', 'Low risk - safe for automatic deployment'
        elif overall_risk == RiskLevel.MEDIUM:
            return 'CANARY', 'Medium risk - deploy via canary rollout'
        elif overall_risk == RiskLevel.HIGH:
            return 'MANUAL_REVIEW', 'High risk - requires manual approval'
        else:  # CRITICAL
            return 'MANUAL_REVIEW', 'Critical risk - must not auto-deploy'
    
    def format_risk_report(self, risk: RiskScore) -> str:
        """Format risk score as human-readable report"""
        lines = []
        lines.append("=" * 70)
        lines.append("RISK ASSESSMENT REPORT")
        lines.append("=" * 70)
        
        # Overall risk with visual indicator
        risk_icons = {
            RiskLevel.LOW: "🟢",
            RiskLevel.MEDIUM: "🟡",
            RiskLevel.HIGH: "🟠",
            RiskLevel.CRITICAL: "🔴"
        }
        icon = risk_icons.get(risk.overall_risk, "⚪")
        lines.append(f"Overall Risk: {icon} {risk.overall_risk.value.upper()}")
        lines.append(f"Risk Score: {risk.risk_score:.1f}/100")
        lines.append(f"Recommendation: {risk.recommendation}")
        lines.append(f"Reasoning: {risk.reasoning}")
        lines.append("")
        
        lines.append("Risk Factors:")
        lines.append(f"  Service Criticality: {risk.service_criticality.name} ({risk.factors['criticality_score']}/5)")
        lines.append(f"  Change Size: {risk.change_size.name} ({risk.factors['change_score']}/5)")
        lines.append(f"    - Lines changed: {risk.factors['lines_changed']}")
        lines.append(f"  Error Severity: {risk.error_severity:.1f}/10")
        lines.append(f"    - Tests failed: {risk.factors['tests_failed']}")
        lines.append(f"    - Lint errors: {risk.factors['lint_errors']}")
        lines.append(f"    - Security issues: {risk.factors['security_issues']}")
        lines.append(f"    - Build failed: {risk.factors['build_failed']}")
        lines.append("")
        
        # Deployment strategy
        lines.append("Deployment Strategy:")
        if risk.recommendation == 'DEPLOY':
            lines.append("  ✓ Auto-deploy to production")
        elif risk.recommendation == 'CANARY':
            lines.append("  ⚠ Canary rollout recommended:")
            lines.append("    1. Deploy to 5% of traffic")
            lines.append("    2. Monitor for 10 minutes")
            lines.append("    3. Gradually increase to 100%")
        else:  # MANUAL_REVIEW
            lines.append("  ✗ Manual review required")
            lines.append("    - Do not auto-deploy")
            lines.append("    - Requires approval from team lead")
        
        lines.append("=" * 70)
        return "\n".join(lines)


# Example usage
if __name__ == "__main__":
    scorer = RiskScorer(config={
        'service_criticality': {
            'payment-service': ServiceCriticality.CRITICAL,
            'analytics-service': ServiceCriticality.LOW
        },
        'low_risk_threshold': 20,
        'medium_risk_threshold': 50,
        'high_risk_threshold': 75
    })
    
    # Scenario 1: Low risk change
    print("=== Scenario 1: Low Risk Change ===")
    risk1 = scorer.calculate_risk(
        service_name='analytics-service',
        patch_result={
            'patch_results': [
                {'lines_added': 5, 'lines_removed': 2}
            ]
        },
        test_result={'passed': True, 'tests_run': 50, 'tests_failed': 0, 'coverage_percentage': 85},
        analysis_result={'passed': True, 'security_scan_passed': True, 'critical': 0, 'high': 0}
    )
    print(scorer.format_risk_report(risk1))
    print()
    
    # Scenario 2: High risk change
    print("=== Scenario 2: High Risk Change ===")
    risk2 = scorer.calculate_risk(
        service_name='payment-service',
        patch_result={
            'patch_results': [
                {'lines_added': 150, 'lines_removed': 80}
            ]
        },
        test_result={'passed': False, 'tests_run': 100, 'tests_failed': 5, 'coverage_percentage': 75},
        analysis_result={'passed': True, 'security_scan_passed': True, 'critical': 0, 'high': 1}
    )
    print(scorer.format_risk_report(risk2))
