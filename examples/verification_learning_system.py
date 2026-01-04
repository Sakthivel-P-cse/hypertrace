#!/usr/bin/env python3
"""
Verification Learning System - Step 9 Component

Learns from every verification to self-tune thresholds and reduce false rollbacks.

HIGH-IMPACT FEATURE: Self-tuning system that improves over time

Author: Step 9 - Verification Loop
Date: 2026-01-02
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict


@dataclass
class VerificationOutcome:
    """Record of a single verification outcome"""
    incident_id: str
    incident_type: str
    fix_type: str
    service_name: str
    
    # Metrics
    metrics_delta: Dict[str, float]  # metric_name -> improvement%
    
    # Outcome
    verification_status: str  # PASSED, FAILED, PARTIAL
    was_rolled_back: bool
    resolution_status: str    # FULLY_RESOLVED, PARTIALLY_RESOLVED, etc.
    
    # Feedback (if rollback was wrong decision)
    false_positive: bool      # Rolled back but shouldn't have
    false_negative: bool      # Didn't rollback but should have
    
    confidence_score: float
    timestamp: str


class VerificationLearningSystem:
    """
    Learns from verification outcomes to improve decision-making
    
    FEATURES:
    - Tracks verification history
    - Identifies patterns
    - Adjusts thresholds based on outcomes
    - Reduces false positives/negatives
    """
    
    def __init__(self, history_file: str = 'verification_history.json'):
        """
        Initialize learning system
        
        Args:
            history_file: Path to history file
        """
        self.history_file = history_file
        self.history: List[VerificationOutcome] = []
        self._load_history()
    
    def record_outcome(self, outcome: VerificationOutcome):
        """Record a verification outcome"""
        self.history.append(outcome)
        self._save_history()
        
        print(f"📝 Recorded verification outcome for {outcome.incident_id}")
        print(f"   Type: {outcome.incident_type} | Fix: {outcome.fix_type}")
        print(f"   Status: {outcome.verification_status} | Rollback: {outcome.was_rolled_back}")
    
    def get_recommendations(self, incident_type: str, fix_type: str, service_name: str) -> Dict:
        """
        Get recommendations based on historical learnings
        
        Returns adjusted thresholds and confidence factors
        """
        print(f"\n🧠 LEARNING SYSTEM RECOMMENDATIONS")
        print(f"Incident Type: {incident_type}")
        print(f"Fix Type: {fix_type}")
        print(f"Service: {service_name}")
        
        # Filter relevant history
        relevant = [
            h for h in self.history
            if h.incident_type == incident_type and h.fix_type == fix_type
        ]
        
        if not relevant:
            print("No historical data for this incident/fix combination")
            return self._default_recommendations()
        
        print(f"Found {len(relevant)} similar cases in history")
        
        # Calculate success rate
        passed = sum(1 for h in relevant if h.verification_status == 'PASSED')
        rolled_back = sum(1 for h in relevant if h.was_rolled_back)
        false_positives = sum(1 for h in relevant if h.false_positive)
        false_negatives = sum(1 for h in relevant if h.false_negative)
        
        success_rate = passed / len(relevant) if relevant else 0.0
        rollback_rate = rolled_back / len(relevant) if relevant else 0.0
        false_positive_rate = false_positives / max(1, rolled_back)
        
        print(f"\nHistorical Performance:")
        print(f"  Success rate: {success_rate*100:.1f}%")
        print(f"  Rollback rate: {rollback_rate*100:.1f}%")
        print(f"  False positive rate: {false_positive_rate*100:.1f}%")
        print(f"  False negatives: {false_negatives}")
        
        # Learn optimal thresholds
        recommendations = {
            'success_rate': success_rate,
            'rollback_rate': rollback_rate,
            'false_positive_rate': false_positive_rate,
            'false_negative_count': false_negatives
        }
        
        # Adjust improvement threshold based on false positives
        if false_positive_rate > 0.2:  # More than 20% FP
            # We're too aggressive, raise threshold
            recommendations['suggested_improvement_threshold'] = 0.15  # 15% instead of 10%
            recommendations['reason'] = "High false positive rate - raising threshold"
        elif false_positive_rate < 0.05 and false_negatives > 0:  # Low FP but some FN
            # We're too conservative, lower threshold
            recommendations['suggested_improvement_threshold'] = 0.08  # 8% instead of 10%
            recommendations['reason'] = "False negatives detected - lowering threshold"
        else:
            recommendations['suggested_improvement_threshold'] = 0.10  # Keep at 10%
            recommendations['reason'] = "Current threshold appears optimal"
        
        # Service-specific confidence adjustment
        service_outcomes = [h for h in relevant if h.service_name == service_name]
        if service_outcomes:
            service_success = sum(1 for h in service_outcomes if h.verification_status == 'PASSED')
            service_success_rate = service_success / len(service_outcomes)
            recommendations['service_success_rate'] = service_success_rate
            recommendations['confidence_multiplier'] = min(1.2, 0.8 + service_success_rate * 0.4)
        else:
            recommendations['confidence_multiplier'] = 1.0
        
        # Metric-specific learnings
        metric_patterns = self._analyze_metric_patterns(relevant)
        recommendations['metric_patterns'] = metric_patterns
        
        print(f"\nRecommendations:")
        print(f"  Suggested improvement threshold: {recommendations['suggested_improvement_threshold']*100:.1f}%")
        print(f"  Confidence multiplier: {recommendations['confidence_multiplier']:.2f}")
        print(f"  Reason: {recommendations['reason']}")
        
        return recommendations
    
    def _analyze_metric_patterns(self, outcomes: List[VerificationOutcome]) -> Dict:
        """Analyze which metrics are most predictive of success"""
        metric_importance = defaultdict(lambda: {'success_avg': 0.0, 'fail_avg': 0.0, 'count': 0})
        
        for outcome in outcomes:
            category = 'success' if outcome.verification_status == 'PASSED' else 'fail'
            
            for metric, delta in outcome.metrics_delta.items():
                metric_importance[metric][f'{category}_avg'] += delta
                metric_importance[metric]['count'] += 1
        
        # Calculate averages
        patterns = {}
        for metric, data in metric_importance.items():
            if data['count'] > 0:
                success_avg = data['success_avg'] / data['count']
                fail_avg = data['fail_avg'] / data['count']
                patterns[metric] = {
                    'success_avg_improvement': success_avg,
                    'fail_avg_improvement': fail_avg,
                    'predictiveness': abs(success_avg - fail_avg)  # Higher diff = more predictive
                }
        
        return patterns
    
    def _default_recommendations(self) -> Dict:
        """Return default recommendations when no history"""
        return {
            'success_rate': 0.0,
            'rollback_rate': 0.0,
            'false_positive_rate': 0.0,
            'false_negative_count': 0,
            'suggested_improvement_threshold': 0.10,
            'confidence_multiplier': 1.0,
            'reason': 'No historical data - using defaults',
            'metric_patterns': {}
        }
    
    def get_statistics(self) -> Dict:
        """Get overall system statistics"""
        if not self.history:
            return {'total_verifications': 0}
        
        total = len(self.history)
        passed = sum(1 for h in self.history if h.verification_status == 'PASSED')
        failed = sum(1 for h in self.history if h.verification_status == 'FAILED')
        partial = sum(1 for h in self.history if h.verification_status == 'PARTIALLY_RESOLVED')
        rolled_back = sum(1 for h in self.history if h.was_rolled_back)
        
        # By incident type
        by_type = defaultdict(int)
        for h in self.history:
            by_type[h.incident_type] += 1
        
        # By fix type
        by_fix = defaultdict(int)
        for h in self.history:
            by_fix[h.fix_type] += 1
        
        return {
            'total_verifications': total,
            'passed': passed,
            'failed': failed,
            'partial': partial,
            'rolled_back': rolled_back,
            'success_rate': passed / total if total > 0 else 0,
            'rollback_rate': rolled_back / total if total > 0 else 0,
            'by_incident_type': dict(by_type),
            'by_fix_type': dict(by_fix)
        }
    
    def _load_history(self):
        """Load history from file"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    data = json.load(f)
                    self.history = [VerificationOutcome(**item) for item in data]
                print(f"📂 Loaded {len(self.history)} historical verifications")
            except Exception as e:
                print(f"⚠️  Failed to load history: {e}")
                self.history = []
        else:
            self.history = []
    
    def _save_history(self):
        """Save history to file"""
        try:
            with open(self.history_file, 'w') as f:
                data = [asdict(outcome) for outcome in self.history]
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"⚠️  Failed to save history: {e}")


# Example usage
if __name__ == "__main__":
    learning_system = VerificationLearningSystem('verification_history.json')
    
    # Simulate recording some outcomes
    print("="*60)
    print("SIMULATING VERIFICATION OUTCOMES")
    print("="*60)
    
    outcomes = [
        VerificationOutcome(
            incident_id='INC-001',
            incident_type='high_latency',
            fix_type='connection_pool_resize',
            service_name='payment-service',
            metrics_delta={'error_rate': 85.0, 'p99_latency': 87.0, 'throughput': 5.0},
            verification_status='PASSED',
            was_rolled_back=False,
            resolution_status='FULLY_RESOLVED',
            false_positive=False,
            false_negative=False,
            confidence_score=92.0,
            timestamp=datetime.now().isoformat()
        ),
        VerificationOutcome(
            incident_id='INC-002',
            incident_type='high_latency',
            fix_type='connection_pool_resize',
            service_name='payment-service',
            metrics_delta={'error_rate': 12.0, 'p99_latency': 15.0, 'throughput': -3.0},
            verification_status='FAILED',
            was_rolled_back=True,
            resolution_status='NOT_RESOLVED',
            false_positive=False,
            false_negative=False,
            confidence_score=35.0,
            timestamp=datetime.now().isoformat()
        ),
        VerificationOutcome(
            incident_id='INC-003',
            incident_type='high_error_rate',
            fix_type='null_check_addition',
            service_name='user-service',
            metrics_delta={'error_rate': 95.0, 'p99_latency': 5.0, 'throughput': 2.0},
            verification_status='PASSED',
            was_rolled_back=False,
            resolution_status='FULLY_RESOLVED',
            false_positive=False,
            false_negative=False,
            confidence_score=98.0,
            timestamp=datetime.now().isoformat()
        )
    ]
    
    for outcome in outcomes:
        learning_system.record_outcome(outcome)
    
    # Get recommendations
    print("\n" + "="*60)
    print("GETTING RECOMMENDATIONS")
    print("="*60)
    
    recommendations = learning_system.get_recommendations(
        incident_type='high_latency',
        fix_type='connection_pool_resize',
        service_name='payment-service'
    )
    
    # Get statistics
    print("\n" + "="*60)
    print("SYSTEM STATISTICS")
    print("="*60)
    
    stats = learning_system.get_statistics()
    print(f"Total verifications: {stats['total_verifications']}")
    print(f"Success rate: {stats['success_rate']*100:.1f}%")
    print(f"Rollback rate: {stats['rollback_rate']*100:.1f}%")
    print(f"\nBy incident type: {stats['by_incident_type']}")
    print(f"By fix type: {stats['by_fix_type']}")
    
    print(f"\n✅ Learning system initialized. History saved to: verification_history.json")
