#!/usr/bin/env python3
"""
Rollback Decision Engine - Step 9 Component

Intelligent decision engine for rollback with guardrails.

HIGH-IMPACT FEATURES:
1. "Don't Roll Back" Guardrails - Prevent catastrophic oscillations
2. Multi-factor decision making (severity, blast radius, service criticality)
3. Rollback confidence scoring
4. Previous version health checking

Author: Step 9 - Verification Loop  
Date: 2026-01-02
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum


class RollbackUrgency(Enum):
    """Urgency level for rollback"""
    IMMEDIATE = "IMMEDIATE"        # < 10 seconds, critical issue
    HIGH = "HIGH"                  # < 1 minute
    MEDIUM = "MEDIUM"              # < 5 minutes
    LOW = "LOW"                    # Manual review recommended
    NONE = "NONE"                  # No rollback needed


class RollbackStrategy(Enum):
    """Rollback strategy"""
    INSTANT = "INSTANT"            # Immediate full rollback
    GRADUAL = "GRADUAL"            # Step-down: 100→75→50→25→0%
    PARTIAL = "PARTIAL"            # Rollback to 50%, keep investigating
    NONE = "NONE"                  # Don't rollback
    ESCALATE = "ESCALATE"          # Escalate to humans, both versions bad


@dataclass
class RollbackDecision:
    """Rollback decision with reasoning"""
    should_rollback: bool
    strategy: RollbackStrategy
    urgency: RollbackUrgency
    confidence: float              # 0-100, confidence in decision
    
    # Reasoning
    primary_reason: str
    all_reasons: List[str]
    risk_factors: List[str]
    
    # Guardrails triggered
    guardrails_triggered: List[str]
    safe_to_rollback: bool         # Is previous version healthy?
    
    # Alternatives
    alternative_actions: List[str]
    
    # Decision details
    severity_score: float          # 0-100
    blast_radius_pct: float
    service_criticality: float     # 0-1
    
    decided_at: str


class RollbackDecisionEngine:
    """
    Intelligent rollback decision engine with guardrails
    
    KEY FEATURES:
    - Prevents rollback if previous version also unhealthy
    - Considers severity, blast radius, service criticality
    - Detects infrastructure vs application issues
    - Provides explainable reasoning
    """
    
    def __init__(self, config: Dict):
        """
        Initialize decision engine
        
        Args:
            config: Rollback configuration
        """
        self.config = config
        
        # Thresholds
        self.critical_error_rate = config.get('critical_error_rate_pct', 5.0)
        self.high_error_rate = config.get('high_error_rate_pct', 2.0)
        
        self.critical_latency_multiplier = config.get('critical_latency_multiplier', 2.0)
        self.high_latency_multiplier = config.get('high_latency_multiplier', 1.5)
        
        self.critical_blast_radius = config.get('critical_blast_radius_pct', 10.0)
        self.high_blast_radius = config.get('high_blast_radius_pct', 5.0)
        
        # Service criticality mapping
        self.service_criticality = config.get('service_criticality', {
            'payment': 0.95,
            'auth': 0.95,
            'user': 0.80,
            'order': 0.75,
            'search': 0.60,
            'recommendation': 0.50,
            'analytics': 0.30
        })
    
    def make_decision(self,
                     verification_result: Dict,
                     service_name: str,
                     previous_version_health: Optional[Dict] = None,
                     current_alerts: Optional[List[Dict]] = None) -> RollbackDecision:
        """
        Make rollback decision based on verification result and context
        
        Args:
            verification_result: Result from PostDeploymentVerifier
            service_name: Service being evaluated
            previous_version_health: Health metrics of previous version
            current_alerts: Current active alerts
        
        Returns:
            RollbackDecision with comprehensive reasoning
        """
        print(f"\n{'='*60}")
        print(f"🤔 ROLLBACK DECISION ENGINE")
        print(f"{'='*60}")
        print(f"Service: {service_name}")
        print(f"Verification Status: {verification_result.get('status', 'UNKNOWN')}")
        
        # Extract key metrics
        metric_comparisons = verification_result.get('metric_comparisons', [])
        overall_improvement = verification_result.get('overall_improvement_pct', 0.0)
        
        # Calculate factors
        severity_score = self._calculate_severity(metric_comparisons, current_alerts)
        blast_radius_pct = self._calculate_blast_radius(verification_result)
        criticality = self._get_service_criticality(service_name)
        
        print(f"\nFactors:")
        print(f"  Severity Score: {severity_score:.1f}/100")
        print(f"  Blast Radius: {blast_radius_pct:.1f}%")
        print(f"  Service Criticality: {criticality:.2f}")
        print(f"  Overall Improvement: {overall_improvement:+.1f}%")
        
        # Check guardrails
        print(f"\n🛡️  Checking Rollback Guardrails...")
        guardrails_triggered, safe_to_rollback = self._check_guardrails(
            verification_result,
            previous_version_health,
            current_alerts
        )
        
        for guardrail in guardrails_triggered:
            print(f"  ⚠️  {guardrail}")
        
        if not safe_to_rollback:
            print(f"  🚨 CRITICAL: Not safe to rollback!")
        
        # Make decision
        decision = self._evaluate_decision(
            verification_result,
            severity_score,
            blast_radius_pct,
            criticality,
            guardrails_triggered,
            safe_to_rollback,
            previous_version_health,
            current_alerts
        )
        
        print(f"\n{'='*60}")
        print(f"📋 DECISION: {decision.strategy.value}")
        print(f"{'='*60}")
        print(f"Should Rollback: {'✅ YES' if decision.should_rollback else '❌ NO'}")
        print(f"Urgency: {decision.urgency.value}")
        print(f"Confidence: {decision.confidence:.1f}/100")
        print(f"\nPrimary Reason: {decision.primary_reason}")
        print(f"\nAll Reasons:")
        for reason in decision.all_reasons:
            print(f"  • {reason}")
        
        if decision.alternative_actions:
            print(f"\nAlternative Actions:")
            for action in decision.alternative_actions:
                print(f"  → {action}")
        
        return decision
    
    def _calculate_severity(self, metric_comparisons: List[Dict], current_alerts: Optional[List[Dict]]) -> float:
        """
        Calculate severity score (0-100) based on metric degradations
        
        Higher score = more severe degradation
        """
        severity = 0.0
        
        for comp in metric_comparisons:
            metric_name = comp.get('metric_name', '')
            improvement_pct = comp.get('improvement_pct', 0.0)
            verdict = comp.get('verdict', 'UNCHANGED')
            
            if verdict == 'DEGRADED':
                # Error rate degradation is most critical
                if metric_name == 'error_rate':
                    if improvement_pct < -self.critical_error_rate:
                        severity += 40  # Very severe
                    elif improvement_pct < -self.high_error_rate:
                        severity += 25  # Severe
                    else:
                        severity += 10  # Moderate
                
                # Latency degradation
                elif 'latency' in metric_name:
                    if improvement_pct < -100:  # 2x worse
                        severity += 30
                    elif improvement_pct < -50:  # 1.5x worse
                        severity += 15
                    else:
                        severity += 5
                
                # Other metrics
                else:
                    severity += 5
        
        # Factor in alerts
        if current_alerts:
            critical_alerts = sum(1 for a in current_alerts if a.get('severity') == 'critical')
            warning_alerts = sum(1 for a in current_alerts if a.get('severity') == 'warning')
            
            severity += critical_alerts * 15
            severity += warning_alerts * 5
        
        return min(100.0, severity)
    
    def _calculate_blast_radius(self, verification_result: Dict) -> float:
        """
        Calculate blast radius (% of users/traffic affected)
        """
        # Get from verification result
        treatment_pct = verification_result.get('treatment_group_size_pct', 100.0)
        
        # If we're at 100%, assume full blast radius
        return treatment_pct
    
    def _get_service_criticality(self, service_name: str) -> float:
        """Get service criticality score (0-1)"""
        # Extract base service name (e.g., 'payment-service' -> 'payment')
        base_name = service_name.split('-')[0].lower()
        
        return self.service_criticality.get(base_name, 0.50)  # Default: medium criticality
    
    def _check_guardrails(self,
                         verification_result: Dict,
                         previous_version_health: Optional[Dict],
                         current_alerts: Optional[List[Dict]]) -> Tuple[List[str], bool]:
        """
        Check rollback guardrails to prevent catastrophic decisions
        
        Returns:
            (guardrails_triggered, safe_to_rollback)
        """
        guardrails = []
        safe_to_rollback = True
        
        # Guardrail 1: Previous version health check
        if previous_version_health:
            prev_error_rate = previous_version_health.get('error_rate', 0.0)
            prev_latency = previous_version_health.get('p99_latency', 0.0)
            
            if prev_error_rate > self.high_error_rate:
                guardrails.append(f"Previous version has high error rate: {prev_error_rate:.2f}%")
                safe_to_rollback = False
            
            if prev_latency > 2000:  # 2 seconds
                guardrails.append(f"Previous version has high latency: {prev_latency:.0f}ms")
                # Don't block rollback for latency alone, but warn
        
        # Guardrail 2: Infrastructure-wide issues
        if current_alerts:
            infra_alerts = [a for a in current_alerts if a.get('type') == 'infrastructure']
            if infra_alerts:
                guardrails.append(f"Infrastructure issues detected: {len(infra_alerts)} alerts")
                # Might be infra problem, not code problem
                safe_to_rollback = False
        
        # Guardrail 3: Both versions degraded (comparing with baseline)
        metric_comparisons = verification_result.get('metric_comparisons', [])
        baseline_degraded_count = 0
        
        for comp in metric_comparisons:
            baseline = comp.get('baseline_value', 0)
            treatment = comp.get('treatment_value', 0)
            
            if baseline > 0:
                degradation = ((treatment - baseline) / baseline) * 100
                if degradation > 20:  # 20% worse than baseline
                    baseline_degraded_count += 1
        
        if baseline_degraded_count >= len(metric_comparisons) / 2:
            guardrails.append("Both versions are worse than baseline - possible infrastructure issue")
            safe_to_rollback = False
        
        # Guardrail 4: External dependency failure
        # Check if alerts mention external services
        if current_alerts:
            external_alerts = [a for a in current_alerts if 'external' in a.get('message', '').lower() or 'downstream' in a.get('message', '').lower()]
            if external_alerts:
                guardrails.append(f"External dependency issues: {len(external_alerts)} alerts")
                # External problem, rollback won't help
        
        return guardrails, safe_to_rollback
    
    def _evaluate_decision(self,
                          verification_result: Dict,
                          severity_score: float,
                          blast_radius_pct: float,
                          criticality: float,
                          guardrails_triggered: List[str],
                          safe_to_rollback: bool,
                          previous_version_health: Optional[Dict],
                          current_alerts: Optional[List[Dict]]) -> RollbackDecision:
        """
        Evaluate and make final rollback decision
        """
        status = verification_result.get('status', 'UNKNOWN')
        overall_improvement = verification_result.get('overall_improvement_pct', 0.0)
        
        reasons = []
        risk_factors = []
        alternatives = []
        
        # Decision logic with guardrails
        
        # Case 1: Verification passed - no rollback
        if status == 'PASSED':
            return RollbackDecision(
                should_rollback=False,
                strategy=RollbackStrategy.NONE,
                urgency=RollbackUrgency.NONE,
                confidence=verification_result.get('confidence_score', 90.0),
                primary_reason="Verification passed - deployment is successful",
                all_reasons=["Metrics improved significantly", "All health gates passed"],
                risk_factors=[],
                guardrails_triggered=guardrails_triggered,
                safe_to_rollback=safe_to_rollback,
                alternative_actions=["Monitor for next 30 minutes in cooldown"],
                severity_score=severity_score,
                blast_radius_pct=blast_radius_pct,
                service_criticality=criticality,
                decided_at=datetime.now().isoformat()
            )
        
        # Case 2: Guardrails prevent rollback
        if not safe_to_rollback:
            reasons.append("Rollback guardrails triggered")
            reasons.extend(guardrails_triggered)
            
            return RollbackDecision(
                should_rollback=False,
                strategy=RollbackStrategy.ESCALATE,
                urgency=RollbackUrgency.HIGH,
                confidence=85.0,
                primary_reason="Cannot rollback - previous version also unhealthy",
                all_reasons=reasons,
                risk_factors=["Previous version has issues", "Possible infrastructure problem"],
                guardrails_triggered=guardrails_triggered,
                safe_to_rollback=False,
                alternative_actions=[
                    "Escalate to on-call engineer",
                    "Check infrastructure health",
                    "Review external dependencies",
                    "Consider emergency hotfix"
                ],
                severity_score=severity_score,
                blast_radius_pct=blast_radius_pct,
                service_criticality=criticality,
                decided_at=datetime.now().isoformat()
            )
        
        # Case 3: Partial success
        if status == 'PARTIALLY_RESOLVED':
            if severity_score < 30:
                # Minor issues, keep deployment
                return RollbackDecision(
                    should_rollback=False,
                    strategy=RollbackStrategy.NONE,
                    urgency=RollbackUrgency.LOW,
                    confidence=65.0,
                    primary_reason="Partial success - issues are minor",
                    all_reasons=[
                        "Most metrics improved",
                        "Some metrics degraded but within acceptable limits",
                        f"Overall improvement: {overall_improvement:+.1f}%"
                    ],
                    risk_factors=["Some metrics still degraded"],
                    guardrails_triggered=guardrails_triggered,
                    safe_to_rollback=safe_to_rollback,
                    alternative_actions=[
                        "Create follow-up incident for tuning",
                        "Monitor closely for next hour",
                        "Consider gradual rollout to 50% if issues persist"
                    ],
                    severity_score=severity_score,
                    blast_radius_pct=blast_radius_pct,
                    service_criticality=criticality,
                    decided_at=datetime.now().isoformat()
                )
            else:
                # Significant issues, partial rollback
                return self._create_rollback_decision(
                    strategy=RollbackStrategy.PARTIAL,
                    urgency=RollbackUrgency.MEDIUM,
                    primary_reason="Partial success with significant issues",
                    reasons=[
                        "Some metrics significantly degraded",
                        f"Severity score: {severity_score:.1f}/100",
                        "Recommend partial rollback to reduce blast radius"
                    ],
                    severity_score=severity_score,
                    blast_radius_pct=blast_radius_pct,
                    criticality=criticality,
                    guardrails_triggered=guardrails_triggered,
                    safe_to_rollback=safe_to_rollback,
                    alternatives=[
                        "Rollback to 50% traffic",
                        "Investigate and hotfix",
                        "Full rollback if issues continue"
                    ]
                )
        
        # Case 4: Verification failed - rollback decision based on severity
        if status == 'FAILED':
            # Critical: Immediate rollback
            if severity_score >= 70 or (criticality >= 0.9 and severity_score >= 50):
                urgency = RollbackUrgency.IMMEDIATE
                strategy = RollbackStrategy.INSTANT
                reasons = [
                    f"Critical severity: {severity_score:.1f}/100",
                    f"Service criticality: {criticality:.2f}",
                    f"Blast radius: {blast_radius_pct:.1f}%"
                ]
            
            # High: Fast rollback
            elif severity_score >= 50 or blast_radius_pct >= self.critical_blast_radius:
                urgency = RollbackUrgency.HIGH
                strategy = RollbackStrategy.INSTANT
                reasons = [
                    f"High severity: {severity_score:.1f}/100",
                    f"Blast radius: {blast_radius_pct:.1f}%"
                ]
            
            # Medium: Gradual rollback
            elif severity_score >= 30:
                urgency = RollbackUrgency.MEDIUM
                strategy = RollbackStrategy.GRADUAL
                reasons = [
                    f"Medium severity: {severity_score:.1f}/100",
                    "Gradual rollback recommended"
                ]
            
            # Low: Manual review
            else:
                urgency = RollbackUrgency.LOW
                strategy = RollbackStrategy.GRADUAL
                reasons = [
                    f"Low severity: {severity_score:.1f}/100",
                    "Manual review recommended"
                ]
            
            return self._create_rollback_decision(
                strategy=strategy,
                urgency=urgency,
                primary_reason=f"Verification failed - {status}",
                reasons=reasons,
                severity_score=severity_score,
                blast_radius_pct=blast_radius_pct,
                criticality=criticality,
                guardrails_triggered=guardrails_triggered,
                safe_to_rollback=safe_to_rollback,
                alternatives=[
                    "Emergency hotfix if root cause identified",
                    "Scale out if capacity issue"
                ]
            )
        
        # Case 5: Budget exceeded or inconclusive
        return self._create_rollback_decision(
            strategy=RollbackStrategy.GRADUAL,
            urgency=RollbackUrgency.MEDIUM,
            primary_reason=f"Verification {status} - rolling back as precaution",
            reasons=[
                f"Status: {status}",
                "Cannot confirm deployment success",
                "Rolling back to be safe"
            ],
            severity_score=severity_score,
            blast_radius_pct=blast_radius_pct,
            criticality=criticality,
            guardrails_triggered=guardrails_triggered,
            safe_to_rollback=safe_to_rollback,
            alternatives=["Extend verification window", "Manual investigation"]
        )
    
    def _create_rollback_decision(self,
                                  strategy: RollbackStrategy,
                                  urgency: RollbackUrgency,
                                  primary_reason: str,
                                  reasons: List[str],
                                  severity_score: float,
                                  blast_radius_pct: float,
                                  criticality: float,
                                  guardrails_triggered: List[str],
                                  safe_to_rollback: bool,
                                  alternatives: List[str]) -> RollbackDecision:
        """Create rollback decision"""
        # Calculate confidence based on factors
        confidence = 70.0
        
        if severity_score > 70:
            confidence += 20
        elif severity_score > 50:
            confidence += 10
        
        if safe_to_rollback:
            confidence += 10
        else:
            confidence -= 20
        
        confidence = max(0.0, min(100.0, confidence))
        
        return RollbackDecision(
            should_rollback=True,
            strategy=strategy,
            urgency=urgency,
            confidence=confidence,
            primary_reason=primary_reason,
            all_reasons=reasons,
            risk_factors=[f"Severity: {severity_score:.1f}/100", f"Blast radius: {blast_radius_pct:.1f}%"],
            guardrails_triggered=guardrails_triggered,
            safe_to_rollback=safe_to_rollback,
            alternative_actions=alternatives,
            severity_score=severity_score,
            blast_radius_pct=blast_radius_pct,
            service_criticality=criticality,
            decided_at=datetime.now().isoformat()
        )


# Example usage
if __name__ == "__main__":
    # Configuration
    config = {
        'critical_error_rate_pct': 5.0,
        'high_error_rate_pct': 2.0,
        'critical_latency_multiplier': 2.0,
        'high_latency_multiplier': 1.5,
        'critical_blast_radius_pct': 10.0,
        'high_blast_radius_pct': 5.0,
        'service_criticality': {
            'payment': 0.95,
            'auth': 0.95,
            'user': 0.80,
            'order': 0.75,
            'search': 0.60
        }
    }
    
    engine = RollbackDecisionEngine(config)
    
    # Scenario 1: Failed verification with high severity
    print("="*60)
    print("SCENARIO 1: CRITICAL FAILURE - SHOULD ROLLBACK")
    print("="*60)
    
    verification_failed = {
        'status': 'FAILED',
        'overall_improvement_pct': -45.0,
        'confidence_score': 30.0,
        'treatment_group_size_pct': 100.0,
        'metric_comparisons': [
            {'metric_name': 'error_rate', 'improvement_pct': -120.0, 'verdict': 'DEGRADED', 'baseline_value': 2.0, 'treatment_value': 4.4},
            {'metric_name': 'p99_latency', 'improvement_pct': -85.0, 'verdict': 'DEGRADED', 'baseline_value': 500, 'treatment_value': 925}
        ]
    }
    
    previous_health_good = {
        'error_rate': 1.5,
        'p99_latency': 450
    }
    
    alerts = [
        {'severity': 'critical', 'message': 'High error rate', 'type': 'application'},
        {'severity': 'warning', 'message': 'Increased latency', 'type': 'application'}
    ]
    
    decision1 = engine.make_decision(
        verification_failed,
        'payment-service',
        previous_health_good,
        alerts
    )
    
    # Scenario 2: Failed but previous version also bad (guardrail)
    print("\n" + "="*60)
    print("SCENARIO 2: BOTH VERSIONS BAD - SHOULD ESCALATE")
    print("="*60)
    
    previous_health_bad = {
        'error_rate': 6.0,  # Also bad!
        'p99_latency': 2500
    }
    
    decision2 = engine.make_decision(
        verification_failed,
        'payment-service',
        previous_health_bad,
        alerts
    )
    
    # Scenario 3: Partial success
    print("\n" + "="*60)
    print("SCENARIO 3: PARTIAL SUCCESS - MIXED RESULTS")
    print("="*60)
    
    verification_partial = {
        'status': 'PARTIALLY_RESOLVED',
        'overall_improvement_pct': 15.0,
        'confidence_score': 65.0,
        'treatment_group_size_pct': 100.0,
        'metric_comparisons': [
            {'metric_name': 'error_rate', 'improvement_pct': 30.0, 'verdict': 'IMPROVED', 'baseline_value': 2.0, 'treatment_value': 1.4},
            {'metric_name': 'throughput', 'improvement_pct': -8.0, 'verdict': 'DEGRADED', 'baseline_value': 1000, 'treatment_value': 920}
        ]
    }
    
    decision3 = engine.make_decision(
        verification_partial,
        'search-service',
        previous_health_good,
        []
    )
    
    # Save results
    results = {
        'scenario_1_critical_rollback': asdict(decision1),
        'scenario_2_guardrail_escalate': asdict(decision2),
        'scenario_3_partial_success': asdict(decision3)
    }
    
    # Convert enums
    for scenario in results.values():
        scenario['strategy'] = scenario['strategy'] if isinstance(scenario['strategy'], str) else scenario['strategy'].value
        scenario['urgency'] = scenario['urgency'] if isinstance(scenario['urgency'], str) else scenario['urgency'].value
    
    with open('rollback_decisions.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Rollback decisions saved to: rollback_decisions.json")
