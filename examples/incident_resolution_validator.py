#!/usr/bin/env python3
"""
Incident Resolution Validator - Step 9 Component

Validates that the original incident is actually resolved.

HIGH-IMPACT FEATURES:
- Original symptom validation
- Alert correlation check
- Business metric validation
- Resolution confidence scoring

Author: Step 9 - Verification Loop
Date: 2026-01-02
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum


class ResolutionStatus(Enum):
    """Resolution validation status"""
    FULLY_RESOLVED = "FULLY_RESOLVED"            # Incident completely resolved
    PARTIALLY_RESOLVED = "PARTIALLY_RESOLVED"    # Some symptoms remain
    NOT_RESOLVED = "NOT_RESOLVED"                # Incident still present
    INCONCLUSIVE = "INCONCLUSIVE"                # Cannot determine


@dataclass
class ResolutionCriteria:
    """Criteria for considering incident resolved"""
    criterion_name: str
    required: bool          # Is this criterion required?
    actual_value: float
    expected_value: float
    threshold: float        # Acceptable deviation
    is_met: bool
    reason: str


@dataclass
class ResolutionResult:
    """Complete incident resolution validation result"""
    status: ResolutionStatus
    incident_id: str
    
    # Resolution criteria
    criteria_met: int
    criteria_total: int
    criteria_details: List[ResolutionCriteria]
    
    # Confidence
    resolution_confidence: float  # 0-100
    
    # Original incident details
    original_symptom: str
    symptom_still_present: bool
    
    # Alert correlation
    original_alerts_count: int
    current_alerts_count: int
    alerts_cleared: bool
    
    # Follow-up actions
    requires_follow_up: bool
    follow_up_reasons: List[str]
    
    # Reasoning
    decision_summary: str
    detailed_analysis: str
    
    validated_at: str


class IncidentResolutionValidator:
    """
    Validates that the original incident is truly resolved
    
    Not just "metrics improved", but "the specific problem is gone"
    """
    
    def __init__(self, config: Dict):
        """
        Initialize validator
        
        Args:
            config: Validation configuration
        """
        self.config = config
        
        # Thresholds
        self.min_resolution_confidence = config.get('min_resolution_confidence', 80.0)
        self.alert_clearance_timeout = config.get('alert_clearance_timeout_minutes', 5)
    
    def validate_resolution(self,
                           incident_details: Dict,
                           verification_result: Dict,
                           current_alerts: Optional[List[Dict]] = None) -> ResolutionResult:
        """
        Validate that the incident is resolved
        
        Args:
            incident_details: Original incident from Step 1
            verification_result: Verification result from Step 9
            current_alerts: Current active alerts
        
        Returns:
            ResolutionResult
        """
        incident_id = incident_details.get('incident_id', 'UNKNOWN')
        
        print(f"\n{'='*60}")
        print(f"✅ INCIDENT RESOLUTION VALIDATION")
        print(f"{'='*60}")
        print(f"Incident ID: {incident_id}")
        print(f"Original Issue: {incident_details.get('summary', 'N/A')}")
        
        # Build resolution criteria
        criteria = self._build_resolution_criteria(incident_details, verification_result)
        
        # Check original symptom
        original_symptom = incident_details.get('symptom', '')
        symptom_present = self._check_symptom_present(
            original_symptom,
            verification_result,
            current_alerts
        )
        
        print(f"\n🔍 Original Symptom Check:")
        print(f"   Symptom: {original_symptom}")
        print(f"   Still present: {'❌ YES' if symptom_present else '✅ NO'}")
        
        # Alert correlation
        original_alert_count = len(incident_details.get('related_alerts', []))
        current_alert_count = len(current_alerts) if current_alerts else 0
        alerts_cleared = current_alert_count == 0
        
        print(f"\n📢 Alert Correlation:")
        print(f"   Original alerts: {original_alert_count}")
        print(f"   Current alerts: {current_alert_count}")
        print(f"   Cleared: {'✅ YES' if alerts_cleared else '❌ NO'}")
        
        # Evaluate criteria
        print(f"\n📋 Resolution Criteria:")
        criteria_met = 0
        required_met = 0
        required_total = 0
        
        for criterion in criteria:
            symbol = "✅" if criterion.is_met else "❌"
            req_mark = " (REQUIRED)" if criterion.required else ""
            print(f"   {symbol} {criterion.criterion_name}{req_mark}")
            print(f"      {criterion.reason}")
            
            if criterion.is_met:
                criteria_met += 1
                if criterion.required:
                    required_met += 1
            
            if criterion.required:
                required_total += 1
        
        # Calculate resolution confidence
        confidence = self._calculate_resolution_confidence(
            criteria,
            criteria_met,
            len(criteria),
            symptom_present,
            alerts_cleared
        )
        
        print(f"\n📊 Resolution Confidence: {confidence:.1f}/100")
        
        # Determine status
        status = self._determine_resolution_status(
            criteria,
            required_met,
            required_total,
            symptom_present,
            confidence
        )
        
        # Check if follow-up needed
        requires_follow_up, follow_up_reasons = self._check_follow_up_needed(
            status,
            criteria,
            symptom_present,
            current_alert_count
        )
        
        # Generate summary
        decision_summary = self._generate_decision_summary(
            status,
            confidence,
            criteria_met,
            len(criteria)
        )
        
        detailed_analysis = self._generate_detailed_analysis(
            incident_details,
            verification_result,
            criteria,
            symptom_present,
            alerts_cleared
        )
        
        print(f"\n{'='*60}")
        print(f"Status: {status.value}")
        print(f"Confidence: {confidence:.1f}/100")
        print(f"Criteria Met: {criteria_met}/{len(criteria)}")
        print(f"Follow-up Required: {'✅ YES' if requires_follow_up else '❌ NO'}")
        print(f"\n{decision_summary}")
        
        return ResolutionResult(
            status=status,
            incident_id=incident_id,
            criteria_met=criteria_met,
            criteria_total=len(criteria),
            criteria_details=criteria,
            resolution_confidence=confidence,
            original_symptom=original_symptom,
            symptom_still_present=symptom_present,
            original_alerts_count=original_alert_count,
            current_alerts_count=current_alert_count,
            alerts_cleared=alerts_cleared,
            requires_follow_up=requires_follow_up,
            follow_up_reasons=follow_up_reasons,
            decision_summary=decision_summary,
            detailed_analysis=detailed_analysis,
            validated_at=datetime.now().isoformat()
        )
    
    def _build_resolution_criteria(self, incident_details: Dict, verification_result: Dict) -> List[ResolutionCriteria]:
        """Build resolution criteria based on incident type"""
        criteria = []
        
        incident_type = incident_details.get('incident_type', 'unknown')
        metric_comparisons = verification_result.get('metric_comparisons', [])
        
        # Extract key metrics
        error_rate_comp = next((c for c in metric_comparisons if c.get('metric_name') == 'error_rate'), None)
        latency_comp = next((c for c in metric_comparisons if 'latency' in c.get('metric_name', '')), None)
        throughput_comp = next((c for c in metric_comparisons if c.get('metric_name') == 'throughput'), None)
        
        # Criterion 1: Error rate improvement (REQUIRED for most incidents)
        if error_rate_comp:
            improvement = error_rate_comp.get('improvement_pct', 0.0)
            is_met = improvement >= 10.0  # At least 10% improvement
            
            criteria.append(ResolutionCriteria(
                criterion_name="Error Rate Improved",
                required=True,
                actual_value=improvement,
                expected_value=10.0,
                threshold=5.0,
                is_met=is_met,
                reason=f"Error rate {'improved' if is_met else 'did not improve enough'} by {improvement:+.1f}% (target: +10%)"
            ))
        
        # Criterion 2: Latency improvement (REQUIRED for latency incidents)
        if latency_comp and 'latency' in incident_type.lower():
            improvement = latency_comp.get('improvement_pct', 0.0)
            is_met = improvement >= 5.0  # At least 5% improvement
            
            criteria.append(ResolutionCriteria(
                criterion_name="Latency Improved",
                required=True,
                actual_value=improvement,
                expected_value=5.0,
                threshold=2.0,
                is_met=is_met,
                reason=f"Latency {'improved' if is_met else 'did not improve enough'} by {improvement:+.1f}% (target: +5%)"
            ))
        
        # Criterion 3: Throughput maintained (REQUIRED)
        if throughput_comp:
            improvement = throughput_comp.get('improvement_pct', 0.0)
            is_met = improvement >= -5.0  # Not more than 5% worse
            
            criteria.append(ResolutionCriteria(
                criterion_name="Throughput Maintained",
                required=True,
                actual_value=improvement,
                expected_value=0.0,
                threshold=5.0,
                is_met=is_met,
                reason=f"Throughput {'maintained' if is_met else 'degraded'} ({improvement:+.1f}%, acceptable: > -5%)"
            ))
        
        # Criterion 4: Metrics stable (OPTIONAL)
        stability_score = verification_result.get('stability_score', 0.0)
        is_met = stability_score >= 70.0
        
        criteria.append(ResolutionCriteria(
            criterion_name="Metrics Stable",
            required=False,
            actual_value=stability_score,
            expected_value=70.0,
            threshold=10.0,
            is_met=is_met,
            reason=f"Stability score: {stability_score:.1f}/100 (target: 70+)"
        ))
        
        # Criterion 5: Verification confidence (OPTIONAL)
        verification_confidence = verification_result.get('confidence_score', 0.0)
        is_met = verification_confidence >= 70.0
        
        criteria.append(ResolutionCriteria(
            criterion_name="Verification Confidence High",
            required=False,
            actual_value=verification_confidence,
            expected_value=70.0,
            threshold=10.0,
            is_met=is_met,
            reason=f"Verification confidence: {verification_confidence:.1f}/100 (target: 70+)"
        ))
        
        return criteria
    
    def _check_symptom_present(self, symptom: str, verification_result: Dict, current_alerts: Optional[List[Dict]]) -> bool:
        """
        Check if the original symptom is still present
        
        This is incident-specific logic
        """
        # Check if any current alerts mention the symptom
        if current_alerts:
            for alert in current_alerts:
                alert_message = alert.get('message', '').lower()
                if symptom.lower() in alert_message:
                    return True
        
        # Check if metrics still show the problem
        metric_comparisons = verification_result.get('metric_comparisons', [])
        
        for comp in metric_comparisons:
            if comp.get('verdict') == 'DEGRADED':
                # If key metrics are still degraded, symptom persists
                return True
        
        # Symptom appears to be resolved
        return False
    
    def _calculate_resolution_confidence(self,
                                        criteria: List[ResolutionCriteria],
                                        criteria_met: int,
                                        criteria_total: int,
                                        symptom_present: bool,
                                        alerts_cleared: bool) -> float:
        """Calculate resolution confidence score (0-100)"""
        confidence = 0.0
        
        # Base: Criteria met
        if criteria_total > 0:
            criteria_ratio = criteria_met / criteria_total
            confidence += criteria_ratio * 50  # Up to 50 points
        
        # Symptom check (most important)
        if not symptom_present:
            confidence += 30  # 30 points for symptom gone
        else:
            confidence -= 20  # Penalty if symptom still present
        
        # Alerts cleared
        if alerts_cleared:
            confidence += 20  # 20 points for alerts cleared
        else:
            confidence -= 10  # Penalty if alerts still firing
        
        # Ensure 0-100 range
        confidence = max(0.0, min(100.0, confidence))
        
        return confidence
    
    def _determine_resolution_status(self,
                                    criteria: List[ResolutionCriteria],
                                    required_met: int,
                                    required_total: int,
                                    symptom_present: bool,
                                    confidence: float) -> ResolutionStatus:
        """Determine overall resolution status"""
        # If symptom still present, not resolved
        if symptom_present:
            return ResolutionStatus.NOT_RESOLVED
        
        # If not all required criteria met, not resolved
        if required_total > 0 and required_met < required_total:
            return ResolutionStatus.PARTIALLY_RESOLVED
        
        # If confidence is high, fully resolved
        if confidence >= self.min_resolution_confidence:
            return ResolutionStatus.FULLY_RESOLVED
        
        # If confidence is moderate, partially resolved
        if confidence >= 60.0:
            return ResolutionStatus.PARTIALLY_RESOLVED
        
        # Low confidence
        return ResolutionStatus.INCONCLUSIVE
    
    def _check_follow_up_needed(self,
                               status: ResolutionStatus,
                               criteria: List[ResolutionCriteria],
                               symptom_present: bool,
                               current_alert_count: int) -> tuple:
        """Determine if follow-up action is needed"""
        requires_follow_up = False
        reasons = []
        
        if status == ResolutionStatus.NOT_RESOLVED:
            requires_follow_up = True
            reasons.append("Incident not resolved - needs further investigation")
        
        if status == ResolutionStatus.PARTIALLY_RESOLVED:
            requires_follow_up = True
            reasons.append("Incident partially resolved - create follow-up ticket for remaining issues")
        
        if symptom_present:
            requires_follow_up = True
            reasons.append("Original symptom still present")
        
        if current_alert_count > 0:
            requires_follow_up = True
            reasons.append(f"{current_alert_count} alerts still active")
        
        # Check if any required criteria not met
        for criterion in criteria:
            if criterion.required and not criterion.is_met:
                requires_follow_up = True
                reasons.append(f"Required criterion not met: {criterion.criterion_name}")
        
        return requires_follow_up, reasons
    
    def _generate_decision_summary(self, status: ResolutionStatus, confidence: float, criteria_met: int, criteria_total: int) -> str:
        """Generate human-readable decision summary"""
        if status == ResolutionStatus.FULLY_RESOLVED:
            return f"✅ Incident FULLY RESOLVED with {confidence:.1f}% confidence. All key criteria met ({criteria_met}/{criteria_total})."
        
        elif status == ResolutionStatus.PARTIALLY_RESOLVED:
            return f"⚠️  Incident PARTIALLY RESOLVED with {confidence:.1f}% confidence. {criteria_met}/{criteria_total} criteria met. Follow-up recommended."
        
        elif status == ResolutionStatus.NOT_RESOLVED:
            return f"❌ Incident NOT RESOLVED. Only {criteria_met}/{criteria_total} criteria met. Further action required."
        
        else:
            return f"❓ INCONCLUSIVE - confidence {confidence:.1f}%. Additional monitoring needed."
    
    def _generate_detailed_analysis(self,
                                   incident_details: Dict,
                                   verification_result: Dict,
                                   criteria: List[ResolutionCriteria],
                                   symptom_present: bool,
                                   alerts_cleared: bool) -> str:
        """Generate detailed analysis text"""
        lines = []
        
        lines.append("DETAILED RESOLUTION ANALYSIS")
        lines.append("="*60)
        lines.append(f"Incident: {incident_details.get('incident_id', 'N/A')}")
        lines.append(f"Type: {incident_details.get('incident_type', 'N/A')}")
        lines.append(f"Original Symptom: {incident_details.get('symptom', 'N/A')}")
        lines.append("")
        
        lines.append("VERIFICATION RESULTS:")
        lines.append(f"  Status: {verification_result.get('status', 'N/A')}")
        lines.append(f"  Overall Improvement: {verification_result.get('overall_improvement_pct', 0):+.1f}%")
        lines.append(f"  Confidence: {verification_result.get('confidence_score', 0):.1f}/100")
        lines.append("")
        
        lines.append("RESOLUTION CRITERIA:")
        for criterion in criteria:
            status_mark = "✅ PASS" if criterion.is_met else "❌ FAIL"
            req_mark = " [REQUIRED]" if criterion.required else " [OPTIONAL]"
            lines.append(f"  {status_mark} {criterion.criterion_name}{req_mark}")
            lines.append(f"     {criterion.reason}")
        lines.append("")
        
        lines.append("SYMPTOM & ALERTS:")
        lines.append(f"  Original symptom present: {'YES ❌' if symptom_present else 'NO ✅'}")
        lines.append(f"  Alerts cleared: {'YES ✅' if alerts_cleared else 'NO ❌'}")
        lines.append("")
        
        lines.append("RECOMMENDATION:")
        if not symptom_present and alerts_cleared:
            lines.append("  ✅ Incident appears fully resolved. Safe to close.")
        else:
            lines.append("  ⚠️  Some issues remain. Follow-up action recommended.")
        
        return "\n".join(lines)


# Example usage
if __name__ == "__main__":
    # Configuration
    config = {
        'min_resolution_confidence': 80.0,
        'alert_clearance_timeout_minutes': 5
    }
    
    validator = IncidentResolutionValidator(config)
    
    # Mock incident details
    incident_details = {
        'incident_id': 'INC-001',
        'incident_type': 'high_latency',
        'summary': 'Payment service timeout',
        'symptom': 'p99 latency > 3 seconds',
        'related_alerts': [
            {'id': 'ALERT-001', 'severity': 'critical', 'message': 'High latency detected'},
            {'id': 'ALERT-002', 'severity': 'warning', 'message': 'Timeout rate increased'}
        ]
    }
    
    # Mock verification result
    verification_result = {
        'status': 'PASSED',
        'overall_improvement_pct': 87.5,
        'confidence_score': 92.0,
        'stability_score': 85.0,
        'metric_comparisons': [
            {'metric_name': 'error_rate', 'improvement_pct': 85.0, 'verdict': 'IMPROVED'},
            {'metric_name': 'p99_latency', 'improvement_pct': 87.0, 'verdict': 'IMPROVED'},
            {'metric_name': 'throughput', 'improvement_pct': 5.0, 'verdict': 'IMPROVED'}
        ]
    }
    
    # No current alerts (resolved)
    current_alerts = []
    
    # Validate resolution
    result = validator.validate_resolution(
        incident_details,
        verification_result,
        current_alerts
    )
    
    # Save result
    result_dict = asdict(result)
    result_dict['status'] = result.status.value
    
    with open('resolution_validation_INC-001.json', 'w') as f:
        json.dump(result_dict, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"✅ Resolution validation saved to: resolution_validation_INC-001.json")
    print(f"Status: {result.status.value}")
    print(f"Confidence: {result.resolution_confidence:.1f}/100")
    print(f"Follow-up needed: {'YES' if result.requires_follow_up else 'NO'}")
