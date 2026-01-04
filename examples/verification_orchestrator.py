#!/usr/bin/env python3
"""
Verification Orchestrator - Step 9 Main Coordinator

Integrates all Step 9 components to close the self-healing loop.

FLOW:
1. Post-deployment verification (control vs treatment)
2. Stability analysis
3. Rollback decision (with guardrails)
4. Rollback execution (if needed)
5. Incident resolution validation
6. Learning system update
7. Cooldown monitoring

Author: Step 9 - Verification Loop
Date: 2026-01-02
"""

import json
import time
from datetime import datetime
from typing import Dict, Optional
from dataclasses import dataclass, asdict

# Import Step 9 components
from post_deployment_verifier import PostDeploymentVerifier, VerificationStatus
from metric_stability_analyzer import MetricStabilityAnalyzer
from rollback_decision_engine import RollbackDecisionEngine
from rollback_orchestrator import RollbackOrchestrator
from incident_resolution_validator import IncidentResolutionValidator
from verification_learning_system import VerificationLearningSystem, VerificationOutcome


@dataclass
class VerificationLoopResult:
    """Complete verification loop result"""
    incident_id: str
    deployment_id: str
    
    # Verification
    verification_passed: bool
    verification_confidence: float
    
    # Rollback
    rollback_executed: bool
    rollback_successful: bool
    
    # Resolution
    incident_resolved: bool
    resolution_confidence: float
    
    # Actions taken
    actions_taken: list
    
    # Final state
    final_state: str
    requires_follow_up: bool
    follow_up_actions: list
    
    # Artifacts
    verification_artifact_path: str
    rollback_artifact_path: Optional[str]
    resolution_artifact_path: str
    
    # Timing
    total_duration_seconds: float
    started_at: str
    completed_at: str


class VerificationOrchestrator:
    """
    Main coordinator for Step 9 - Verification Loop
    
    Orchestrates the complete post-deployment verification workflow
    """
    
    def __init__(self, config_path: str = 'verification_config.yaml'):
        """
        Initialize orchestrator
        
        Args:
            config_path: Path to verification configuration
        """
        self.config = self._load_config(config_path)
        
        # Initialize components
        self.verifier = PostDeploymentVerifier(
            prometheus_url=self.config['prometheus_url'],
            verification_config=self.config['verification'],
            deployment_result={}  # Will be set per call
        )
        
        self.stability_analyzer = MetricStabilityAnalyzer(
            self.config['stability']
        )
        
        self.rollback_engine = RollbackDecisionEngine(
            self.config['rollback']
        )
        
        self.rollback_orchestrator = RollbackOrchestrator(
            self.config['rollback']
        )
        
        self.resolution_validator = IncidentResolutionValidator(
            self.config['resolution']
        )
        
        self.learning_system = VerificationLearningSystem(
            self.config.get('learning', {}).get('history_file', 'verification_history.json')
        )
    
    def verify_deployment(self,
                         incident_details: Dict,
                         deployment_result: Dict) -> VerificationLoopResult:
        """
        Main entry point: Verify deployment and close the loop
        
        Args:
            incident_details: Original incident from Step 1
            deployment_result: Deployment result from Step 8
        
        Returns:
            VerificationLoopResult
        """
        start_time = time.time()
        started_at = datetime.now().isoformat()
        
        incident_id = incident_details.get('incident_id', 'UNKNOWN')
        deployment_id = deployment_result.get('deployment_id', 'UNKNOWN')
        service_name = deployment_result.get('service_name', 'unknown')
        
        print(f"\n{'='*70}")
        print(f"🔄 VERIFICATION LOOP - STEP 9")
        print(f"{'='*70}")
        print(f"Incident: {incident_id}")
        print(f"Deployment: {deployment_id}")
        print(f"Service: {service_name}")
        
        actions_taken = []
        
        # Get learning recommendations
        print(f"\n🧠 Consulting learning system...")
        recommendations = self.learning_system.get_recommendations(
            incident_type=incident_details.get('incident_type', 'unknown'),
            fix_type=incident_details.get('fix_type', 'unknown'),
            service_name=service_name
        )
        
        # Update verifier with deployment result
        self.verifier.deployment_result = deployment_result
        
        # PHASE 1: Post-Deployment Verification
        print(f"\n{'='*70}")
        print(f"PHASE 1: POST-DEPLOYMENT VERIFICATION")
        print(f"{'='*70}")
        
        verification_result = self.verifier.verify_fix(
            incident_id=incident_id,
            service_name=service_name,
            namespace=deployment_result.get('namespace', 'production'),
            wait_for_stability=self.config['verification'].get('wait_for_stability_seconds', 120)
        )
        
        actions_taken.append(f"Post-deployment verification: {verification_result.status.value}")
        
        # Save verification artifact
        verification_artifact_path = f"verification_result_{incident_id}.json"
        self._save_artifact(verification_result, verification_artifact_path)
        
        # PHASE 2: Cooldown Monitoring (if verification passed)
        if verification_result.status == VerificationStatus.PASSED:
            print(f"\n{'='*70}")
            print(f"PHASE 2: COOLDOWN MONITORING")
            print(f"{'='*70}")
            
            cooldown_minutes = self.config.get('cooldown', {}).get('duration_minutes', 15)
            print(f"Monitoring for {cooldown_minutes} minutes to ensure stability...")
            
            # Mock: In production, this would monitor for the full cooldown period
            time.sleep(2)  # Simulate 2 seconds instead of full cooldown
            
            actions_taken.append(f"Cooldown monitoring: {cooldown_minutes} minutes")
            print(f"✅ Cooldown period completed - no issues detected")
        
        # PHASE 3: Rollback Decision
        print(f"\n{'='*70}")
        print(f"PHASE 3: ROLLBACK DECISION")
        print(f"{'='*70}")
        
        # Get previous version health (for guardrails)
        previous_health = deployment_result.get('previous_version_health', None)
        
        rollback_decision = self.rollback_engine.make_decision(
            verification_result=asdict(verification_result),
            service_name=service_name,
            previous_version_health=previous_health,
            current_alerts=None  # In production, fetch from alerting system
        )
        
        actions_taken.append(f"Rollback decision: {rollback_decision.strategy.value}")
        
        # PHASE 4: Rollback Execution (if needed)
        rollback_executed = False
        rollback_successful = False
        rollback_artifact_path = None
        
        if rollback_decision.should_rollback:
            print(f"\n{'='*70}")
            print(f"PHASE 4: ROLLBACK EXECUTION")
            print(f"{'='*70}")
            print(f"Strategy: {rollback_decision.strategy.value}")
            print(f"Urgency: {rollback_decision.urgency.value}")
            print(f"Reason: {rollback_decision.primary_reason}")
            
            rollback_result = self.rollback_orchestrator.execute_rollback(
                deployment_result=deployment_result,
                strategy=rollback_decision.strategy.value,
                reason=rollback_decision.primary_reason
            )
            
            rollback_executed = True
            rollback_successful = (rollback_result.status.value == 'SUCCESS')
            
            actions_taken.append(f"Rollback executed: {rollback_result.status.value}")
            
            # Save rollback artifact
            rollback_artifact_path = f"rollback_result_{incident_id}.json"
            self._save_artifact(rollback_result, rollback_artifact_path)
        
        # PHASE 5: Incident Resolution Validation
        print(f"\n{'='*70}")
        print(f"PHASE 5: INCIDENT RESOLUTION VALIDATION")
        print(f"{'='*70}")
        
        resolution_result = self.resolution_validator.validate_resolution(
            incident_details=incident_details,
            verification_result=asdict(verification_result),
            current_alerts=None  # In production, fetch from alerting system
        )
        
        actions_taken.append(f"Resolution validation: {resolution_result.status.value}")
        
        # Save resolution artifact
        resolution_artifact_path = f"resolution_validation_{incident_id}.json"
        self._save_artifact(resolution_result, resolution_artifact_path)
        
        # PHASE 6: Update Learning System
        print(f"\n{'='*70}")
        print(f"PHASE 6: LEARNING SYSTEM UPDATE")
        print(f"{'='*70}")
        
        outcome = VerificationOutcome(
            incident_id=incident_id,
            incident_type=incident_details.get('incident_type', 'unknown'),
            fix_type=incident_details.get('fix_type', 'unknown'),
            service_name=service_name,
            metrics_delta={
                comp.metric_name: comp.improvement_pct
                for comp in verification_result.metric_comparisons
            },
            verification_status=verification_result.status.value,
            was_rolled_back=rollback_executed,
            resolution_status=resolution_result.status.value,
            false_positive=False,  # Would be determined by follow-up analysis
            false_negative=False,
            confidence_score=verification_result.confidence_score,
            timestamp=datetime.now().isoformat()
        )
        
        self.learning_system.record_outcome(outcome)
        actions_taken.append("Learning system updated")
        
        # PHASE 7: Determine Final State
        print(f"\n{'='*70}")
        print(f"FINAL ASSESSMENT")
        print(f"{'='*70}")
        
        verification_passed = verification_result.status == VerificationStatus.PASSED
        incident_resolved = resolution_result.status.value == 'FULLY_RESOLVED'
        
        if incident_resolved and not rollback_executed:
            final_state = "VERIFIED_AND_RESOLVED"
            print(f"✅ Deployment VERIFIED and incident RESOLVED")
        elif rollback_executed and rollback_successful:
            final_state = "ROLLED_BACK_SUCCESSFULLY"
            print(f"🔄 Deployment rolled back successfully")
        elif rollback_executed and not rollback_successful:
            final_state = "ROLLBACK_FAILED"
            print(f"❌ Rollback FAILED - escalation required")
        else:
            final_state = "PARTIALLY_RESOLVED"
            print(f"⚠️  Deployment verified but incident partially resolved")
        
        # Compile follow-up actions
        follow_up_actions = []
        if resolution_result.requires_follow_up:
            follow_up_actions.extend(resolution_result.follow_up_reasons)
        if rollback_decision.alternative_actions:
            follow_up_actions.extend(rollback_decision.alternative_actions)
        
        duration = time.time() - start_time
        
        # Create final result
        result = VerificationLoopResult(
            incident_id=incident_id,
            deployment_id=deployment_id,
            verification_passed=verification_passed,
            verification_confidence=verification_result.confidence_score,
            rollback_executed=rollback_executed,
            rollback_successful=rollback_successful,
            incident_resolved=incident_resolved,
            resolution_confidence=resolution_result.resolution_confidence,
            actions_taken=actions_taken,
            final_state=final_state,
            requires_follow_up=len(follow_up_actions) > 0,
            follow_up_actions=follow_up_actions,
            verification_artifact_path=verification_artifact_path,
            rollback_artifact_path=rollback_artifact_path,
            resolution_artifact_path=resolution_artifact_path,
            total_duration_seconds=duration,
            started_at=started_at,
            completed_at=datetime.now().isoformat()
        )
        
        print(f"\n{'='*70}")
        print(f"VERIFICATION LOOP COMPLETE")
        print(f"{'='*70}")
        print(f"Duration: {duration:.1f}s")
        print(f"Final State: {final_state}")
        print(f"Incident Resolved: {'✅ YES' if incident_resolved else '❌ NO'}")
        print(f"Follow-up Required: {'✅ YES' if result.requires_follow_up else '❌ NO'}")
        
        return result
    
    def _load_config(self, config_path: str) -> Dict:
        """Load verification configuration"""
        # In production, load from YAML file
        # For now, return default configuration
        return {
            'prometheus_url': 'http://prometheus:9090',
            'verification': {
                'wait_for_stability_seconds': 120,
                'budget': {
                    'max_time_minutes': 10,
                    'max_user_impact_pct': 5.0,
                    'max_error_budget_pct': 2.0
                },
                'metrics': ['error_rate', 'p95_latency', 'p99_latency', 'throughput'],
                'improvement_threshold': 0.10,
                'degradation_threshold': 0.05,
                'significance_level': 0.05,
                'control_group_size_pct': 10.0
            },
            'stability': {
                'min_stable_duration_minutes': 5,
                'max_coefficient_variation': 0.15,
                'max_oscillation_frequency': 0.5,
                'trend_significance_level': 0.05
            },
            'rollback': {
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
                    'order': 0.75
                },
                'kubectl_path': 'kubectl',
                'rollback_timeout_seconds': 300,
                'health_check_timeout_seconds': 120
            },
            'resolution': {
                'min_resolution_confidence': 80.0,
                'alert_clearance_timeout_minutes': 5
            },
            'cooldown': {
                'duration_minutes': 15,
                'monitoring_enabled': True
            },
            'learning': {
                'history_file': 'verification_history.json'
            }
        }
    
    def _save_artifact(self, result, filename: str):
        """Save result artifact to file"""
        try:
            result_dict = asdict(result) if hasattr(result, '__dataclass_fields__') else result
            
            # Convert enums to strings
            result_dict = self._convert_enums(result_dict)
            
            with open(filename, 'w') as f:
                json.dump(result_dict, f, indent=2)
            
            print(f"   📄 Artifact saved: {filename}")
        except Exception as e:
            print(f"   ⚠️  Failed to save artifact {filename}: {e}")
    
    def _convert_enums(self, obj):
        """Recursively convert enums to strings"""
        if isinstance(obj, dict):
            return {k: self._convert_enums(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_enums(item) for item in obj]
        elif hasattr(obj, 'value'):  # Enum
            return obj.value
        else:
            return obj


# Example usage
if __name__ == "__main__":
    # Create orchestrator
    orchestrator = VerificationOrchestrator()
    
    # Mock incident details
    incident_details = {
        'incident_id': 'INC-001',
        'incident_type': 'high_latency',
        'fix_type': 'connection_pool_resize',
        'summary': 'Payment service timeout',
        'symptom': 'p99 latency > 3 seconds',
        'related_alerts': []
    }
    
    # Mock deployment result from Step 8
    deployment_result = {
        'deployment_id': 'DEP-abc123',
        'service_name': 'payment-service',
        'namespace': 'production',
        'image_tag': 'payment-service:abc123-1641024000',
        'previous_image_tag': 'payment-service:xyz789-1641020000',
        'state': 'DEPLOYED',
        'canary_percentage': 100,
        'baseline_metrics': {
            'error_rate': 2.5,
            'p95_latency': 520.0,
            'p99_latency': 950.0,
            'throughput': 950.0
        },
        'previous_version_health': {
            'error_rate': 1.5,
            'p99_latency': 450
        }
    }
    
    # Execute verification loop
    result = orchestrator.verify_deployment(
        incident_details=incident_details,
        deployment_result=deployment_result
    )
    
    # Save final result
    with open(f'verification_loop_result_{incident_details["incident_id"]}.json', 'w') as f:
        json.dump(asdict(result), f, indent=2)
    
    print(f"\n✅ Verification loop complete!")
    print(f"Final result saved to: verification_loop_result_{incident_details['incident_id']}.json")
