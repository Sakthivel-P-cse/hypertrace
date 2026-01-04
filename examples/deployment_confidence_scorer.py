#!/usr/bin/env python3
"""
Deployment Confidence Scorer for Step 8: Deployment Automation

Calculates deployment confidence based on:
- Safety gate results (Step 7)
- Canary health metrics
- Blast radius
- Historical deployment success

Provides quantitative justification for deployment decisions.
"""

import json
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum


class DeploymentDecision(Enum):
    """Deployment decision based on confidence"""
    AUTO_PROMOTE = "auto_promote"      # High confidence, proceed automatically
    MANUAL_REVIEW = "manual_review"    # Medium confidence, require approval
    ROLLBACK = "rollback"              # Low confidence, abort deployment


@dataclass
class ConfidenceFactors:
    """Individual factors contributing to confidence score"""
    safety_score: float           # From Step 7 safety gates (0-1)
    canary_health: float          # From canary metrics (0-1)
    blast_radius: float           # Service criticality/impact (0-1, lower is better)
    historical_success: float     # Past deployment success rate (0-1)
    change_complexity: float      # Code change complexity (0-1, lower is better)
    test_coverage: float          # Test coverage (0-1)
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class DeploymentConfidence:
    """Deployment confidence score and decision"""
    overall_score: float          # 0-100
    decision: DeploymentDecision
    factors: ConfidenceFactors
    reasoning: List[str]
    threshold_auto: float
    threshold_manual: float
    timestamp: datetime
    
    def to_dict(self) -> Dict:
        return {
            'overall_score': self.overall_score,
            'decision': self.decision.value,
            'factors': self.factors.to_dict(),
            'reasoning': self.reasoning,
            'thresholds': {
                'auto_promote': self.threshold_auto,
                'manual_review': self.threshold_manual
            },
            'timestamp': self.timestamp.isoformat()
        }


class DeploymentConfidenceScorer:
    """Calculate deployment confidence score"""
    
    def __init__(
        self,
        threshold_auto: float = 80.0,
        threshold_manual: float = 60.0,
        weights: Optional[Dict[str, float]] = None
    ):
        """
        Initialize confidence scorer
        
        Args:
            threshold_auto: Minimum score for auto-promotion (0-100)
            threshold_manual: Minimum score for manual review (0-100)
            weights: Custom weights for factors (default: equal weights)
        """
        self.threshold_auto = threshold_auto
        self.threshold_manual = threshold_manual
        
        # Default weights (must sum to 1.0)
        self.weights = weights or {
            'safety_score': 0.30,        # Safety gates most important
            'canary_health': 0.25,       # Canary metrics critical
            'blast_radius': 0.15,        # Impact matters
            'historical_success': 0.10,  # Past performance
            'change_complexity': 0.10,   # Change risk
            'test_coverage': 0.10        # Test quality
        }
        
        # Validate weights
        total_weight = sum(self.weights.values())
        if abs(total_weight - 1.0) > 0.01:
            raise ValueError(f"Weights must sum to 1.0, got {total_weight}")
    
    def calculate_confidence(
        self,
        safety_result: Dict,
        canary_result: Optional[Dict] = None,
        service_name: str = "unknown",
        deployment_history: Optional[List[Dict]] = None
    ) -> DeploymentConfidence:
        """
        Calculate overall deployment confidence
        
        Args:
            safety_result: Result from Step 7 safety gates
            canary_result: Result from canary health gates (optional)
            service_name: Name of service being deployed
            deployment_history: Historical deployment data
        
        Returns:
            DeploymentConfidence with score and decision
        """
        
        # Extract factors
        factors = self._extract_factors(
            safety_result,
            canary_result,
            service_name,
            deployment_history
        )
        
        # Calculate weighted score
        score = self._calculate_weighted_score(factors)
        
        # Make decision
        decision = self._make_decision(score)
        
        # Generate reasoning
        reasoning = self._generate_reasoning(factors, score, decision)
        
        return DeploymentConfidence(
            overall_score=score,
            decision=decision,
            factors=factors,
            reasoning=reasoning,
            threshold_auto=self.threshold_auto,
            threshold_manual=self.threshold_manual,
            timestamp=datetime.now()
        )
    
    def _extract_factors(
        self,
        safety_result: Dict,
        canary_result: Optional[Dict],
        service_name: str,
        deployment_history: Optional[List[Dict]]
    ) -> ConfidenceFactors:
        """Extract confidence factors from inputs"""
        
        # Safety score from Step 7
        safety_score = self._calculate_safety_score(safety_result)
        
        # Canary health from metrics
        canary_health = self._calculate_canary_health(canary_result) if canary_result else 1.0
        
        # Blast radius (service criticality)
        blast_radius = self._calculate_blast_radius(service_name)
        
        # Historical success rate
        historical_success = self._calculate_historical_success(deployment_history)
        
        # Change complexity
        change_complexity = self._calculate_change_complexity(safety_result)
        
        # Test coverage
        test_coverage = self._extract_test_coverage(safety_result)
        
        return ConfidenceFactors(
            safety_score=safety_score,
            canary_health=canary_health,
            blast_radius=blast_radius,
            historical_success=historical_success,
            change_complexity=change_complexity,
            test_coverage=test_coverage
        )
    
    def _calculate_safety_score(self, safety_result: Dict) -> float:
        """Calculate normalized safety score from Step 7"""
        
        if not safety_result.get('passed', False):
            return 0.0
        
        # Extract check results
        checks = safety_result.get('results', {})
        
        passed_checks = 0
        total_checks = 0
        
        for check_name, check_result in checks.items():
            if isinstance(check_result, dict) and 'passed' in check_result:
                total_checks += 1
                if check_result['passed']:
                    passed_checks += 1
        
        if total_checks == 0:
            return 0.5  # Unknown, neutral score
        
        return passed_checks / total_checks
    
    def _calculate_canary_health(self, canary_result: Dict) -> float:
        """Calculate normalized canary health score"""
        
        if not canary_result:
            return 1.0  # No canary data, assume healthy
        
        if not canary_result.get('passed', True):
            return 0.0
        
        passed_gates = canary_result.get('passed_gates', 0)
        total_gates = canary_result.get('total_gates', 1)
        
        return passed_gates / total_gates if total_gates > 0 else 0.5
    
    def _calculate_blast_radius(self, service_name: str) -> float:
        """
        Calculate blast radius (0-1, lower is better)
        Based on service criticality
        """
        
        # Service criticality mapping
        critical_services = {
            'payment-service': 0.9,
            'auth-service': 0.9,
            'user-service': 0.8,
            'order-service': 0.7,
            'notification-service': 0.5,
            'analytics-service': 0.3,
            'logging-service': 0.2
        }
        
        # Higher criticality = higher blast radius (worse for confidence)
        criticality = critical_services.get(service_name, 0.5)
        
        # Invert for confidence (lower blast radius is better)
        return 1.0 - criticality
    
    def _calculate_historical_success(self, deployment_history: Optional[List[Dict]]) -> float:
        """Calculate historical deployment success rate"""
        
        if not deployment_history:
            return 0.7  # Default, neutral-positive assumption
        
        # Look at last 10 deployments
        recent_deployments = deployment_history[-10:]
        
        if not recent_deployments:
            return 0.7
        
        successful = sum(1 for d in recent_deployments if d.get('success', False))
        
        return successful / len(recent_deployments)
    
    def _calculate_change_complexity(self, safety_result: Dict) -> float:
        """
        Calculate change complexity (0-1, lower is better)
        Based on code changes
        """
        
        # Extract change metrics
        patches_applied = safety_result.get('patches_applied', 0)
        files_changed = len(safety_result.get('changed_files', []))
        
        # Simple heuristic: more changes = higher complexity
        if patches_applied == 0:
            return 1.0  # No changes, lowest complexity
        
        # Normalize complexity (1-10 patches = 0.1-1.0 complexity)
        complexity = min(patches_applied / 10, 1.0)
        
        # Invert for confidence (lower complexity is better)
        return 1.0 - complexity
    
    def _extract_test_coverage(self, safety_result: Dict) -> float:
        """Extract test coverage from safety results"""
        
        results = safety_result.get('results', {})
        test_result = results.get('tests', {})
        
        coverage = test_result.get('coverage', 0.0)
        
        # Normalize to 0-1
        return coverage / 100.0 if coverage > 1 else coverage
    
    def _calculate_weighted_score(self, factors: ConfidenceFactors) -> float:
        """Calculate weighted confidence score (0-100)"""
        
        score = 0.0
        
        score += factors.safety_score * self.weights['safety_score']
        score += factors.canary_health * self.weights['canary_health']
        score += factors.blast_radius * self.weights['blast_radius']
        score += factors.historical_success * self.weights['historical_success']
        score += factors.change_complexity * self.weights['change_complexity']
        score += factors.test_coverage * self.weights['test_coverage']
        
        # Scale to 0-100
        return score * 100.0
    
    def _make_decision(self, score: float) -> DeploymentDecision:
        """Make deployment decision based on score"""
        
        if score >= self.threshold_auto:
            return DeploymentDecision.AUTO_PROMOTE
        elif score >= self.threshold_manual:
            return DeploymentDecision.MANUAL_REVIEW
        else:
            return DeploymentDecision.ROLLBACK
    
    def _generate_reasoning(
        self,
        factors: ConfidenceFactors,
        score: float,
        decision: DeploymentDecision
    ) -> List[str]:
        """Generate human-readable reasoning"""
        
        reasoning = []
        
        # Overall score
        reasoning.append(f"Overall confidence: {score:.1f}/100")
        
        # Factor breakdown
        reasoning.append("Factor breakdown:")
        reasoning.append(f"  • Safety gates: {factors.safety_score*100:.1f}%")
        reasoning.append(f"  • Canary health: {factors.canary_health*100:.1f}%")
        reasoning.append(f"  • Blast radius: {factors.blast_radius*100:.1f}% (lower is safer)")
        reasoning.append(f"  • Historical success: {factors.historical_success*100:.1f}%")
        reasoning.append(f"  • Change complexity: {factors.change_complexity*100:.1f}% (lower is riskier)")
        reasoning.append(f"  • Test coverage: {factors.test_coverage*100:.1f}%")
        
        # Decision reasoning
        if decision == DeploymentDecision.AUTO_PROMOTE:
            reasoning.append(f"✓ Score >= {self.threshold_auto} → AUTO-PROMOTE")
            reasoning.append("All checks passed, safe to deploy automatically")
        elif decision == DeploymentDecision.MANUAL_REVIEW:
            reasoning.append(f"⚠ Score {self.threshold_manual}-{self.threshold_auto} → MANUAL REVIEW REQUIRED")
            reasoning.append("Some concerns detected, human approval recommended")
        else:
            reasoning.append(f"✗ Score < {self.threshold_manual} → ROLLBACK")
            reasoning.append("Confidence too low, abort deployment")
        
        # Key concerns
        concerns = []
        if factors.safety_score < 0.8:
            concerns.append("Low safety gate score")
        if factors.canary_health < 0.8:
            concerns.append("Canary health issues detected")
        if factors.blast_radius < 0.5:
            concerns.append("High blast radius (critical service)")
        if factors.historical_success < 0.7:
            concerns.append("Poor historical success rate")
        if factors.change_complexity < 0.5:
            concerns.append("High change complexity")
        if factors.test_coverage < 0.7:
            concerns.append("Insufficient test coverage")
        
        if concerns:
            reasoning.append("Key concerns:")
            for concern in concerns:
                reasoning.append(f"  ⚠ {concern}")
        
        return reasoning
    
    def save_confidence_report(self, confidence: DeploymentConfidence, output_path: str):
        """Save confidence report as JSON"""
        
        with open(output_path, 'w') as f:
            json.dump(confidence.to_dict(), f, indent=2)
        
        print(f"✓ Confidence report saved: {output_path}")


# Example usage
if __name__ == "__main__":
    # Mock safety result from Step 7
    safety_result = {
        'passed': True,
        'results': {
            'tests': {
                'passed': True,
                'tests_run': 127,
                'tests_passed': 127,
                'coverage': 85.3
            },
            'linting': {'passed': True},
            'static_analysis': {'passed': True},
            'build': {'passed': True}
        },
        'patches_applied': 3,
        'changed_files': ['service.py', 'handler.py']
    }
    
    # Mock canary result
    canary_result = {
        'passed': True,
        'total_gates': 6,
        'passed_gates': 6,
        'failed_gates': 0
    }
    
    # Mock deployment history
    deployment_history = [
        {'success': True},
        {'success': True},
        {'success': True},
        {'success': False},
        {'success': True}
    ]
    
    # Calculate confidence
    scorer = DeploymentConfidenceScorer()
    
    confidence = scorer.calculate_confidence(
        safety_result=safety_result,
        canary_result=canary_result,
        service_name='payment-service',
        deployment_history=deployment_history
    )
    
    print("="*80)
    print("DEPLOYMENT CONFIDENCE REPORT")
    print("="*80)
    print(f"\nScore: {confidence.overall_score:.1f}/100")
    print(f"Decision: {confidence.decision.value.upper()}")
    print(f"\nReasoning:")
    for line in confidence.reasoning:
        print(line)
