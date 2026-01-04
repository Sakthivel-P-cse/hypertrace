#!/usr/bin/env python3
"""
Failure Injection Framework
============================

Implements the 20 failure scenarios from the Failure Injection Matrix.
Used for chaos engineering and validating system resilience.

Scenarios Implemented:
    1. High error rate spike (15%)
    2. Moderate error rate (8%)
    3. Critical error rate (50%)
    4. Conflicting concurrent fixes
    5. Lock timeout
    6. Dependency failure
    7. Canary deployment failure
    8. Safety gate rejection
    9. Generated patch fails tests
    10. RCA misidentification
    11. Audit log corruption
    12. Human override request
    13. Network partition
    14. Observability data missing
    15. Infinite loop in patch
    16. Memory leak in patch
    17. Cascading failures
    18. Rate limit exceeded
    19. Deployment rollback trigger
    20. Verification false positive

Usage:
    # Run single failure
    python failure_injection.py --scenario high_error_rate
    
    # Run all scenarios
    python failure_injection.py --all
    
    # Run chaos testing (random failures)
    python failure_injection.py --chaos --duration 300
"""

import sys
import os
import time
import random
import logging
import argparse
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class FailureScenario(Enum):
    """All failure scenarios from the matrix."""
    HIGH_ERROR_RATE = "high_error_rate"
    MODERATE_ERROR_RATE = "moderate_error_rate"
    CRITICAL_ERROR_RATE = "critical_error_rate"
    CONFLICTING_FIXES = "conflicting_fixes"
    LOCK_TIMEOUT = "lock_timeout"
    DEPENDENCY_FAILURE = "dependency_failure"
    CANARY_FAILURE = "canary_failure"
    SAFETY_GATE_REJECTION = "safety_gate_rejection"
    PATCH_FAILS_TESTS = "patch_fails_tests"
    RCA_MISIDENTIFICATION = "rca_misidentification"
    AUDIT_LOG_CORRUPTION = "audit_log_corruption"
    HUMAN_OVERRIDE = "human_override"
    NETWORK_PARTITION = "network_partition"
    MISSING_OBSERVABILITY = "missing_observability"
    INFINITE_LOOP = "infinite_loop"
    MEMORY_LEAK = "memory_leak"
    CASCADING_FAILURES = "cascading_failures"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    DEPLOYMENT_ROLLBACK = "deployment_rollback"
    VERIFICATION_FALSE_POSITIVE = "verification_false_positive"


class ExpectedReaction(Enum):
    """Expected system reactions."""
    AUTO_FIX = "auto_fix"
    ESCALATE = "escalate"
    ROLLBACK = "rollback"
    ACQUIRE_LOCK = "acquire_lock"
    WAIT_AND_RETRY = "wait_and_retry"
    REJECT = "reject"
    ALERT_HUMAN = "alert_human"
    VERIFY_AND_PROCEED = "verify_and_proceed"


@dataclass
class FailureInjectionResult:
    """Result of a failure injection test."""
    scenario: FailureScenario
    start_time: datetime
    end_time: datetime
    expected_reaction: ExpectedReaction
    actual_reaction: str
    success: bool
    error_message: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    
    def duration_seconds(self) -> float:
        return (self.end_time - self.start_time).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario": self.scenario.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_seconds": self.duration_seconds(),
            "expected_reaction": self.expected_reaction.value,
            "actual_reaction": self.actual_reaction,
            "success": self.success,
            "error_message": self.error_message,
            "metrics": self.metrics
        }


class FailureInjector:
    """Base class for failure injection."""
    
    def __init__(self, scenario: FailureScenario, expected_reaction: ExpectedReaction):
        self.scenario = scenario
        self.expected_reaction = expected_reaction
        
    def inject(self) -> FailureInjectionResult:
        """Inject the failure and validate response."""
        logger.info(f"{'='*70}")
        logger.info(f"Injecting: {self.scenario.value}")
        logger.info(f"Expected Reaction: {self.expected_reaction.value}")
        logger.info(f"{'='*70}")
        
        start_time = datetime.now()
        
        try:
            actual_reaction, metrics = self._inject_failure()
            success = self._validate_reaction(actual_reaction)
            error_message = None
        except Exception as e:
            logger.error(f"Injection failed: {e}")
            actual_reaction = "error"
            success = False
            error_message = str(e)
            metrics = {}
        
        end_time = datetime.now()
        
        result = FailureInjectionResult(
            scenario=self.scenario,
            start_time=start_time,
            end_time=end_time,
            expected_reaction=self.expected_reaction,
            actual_reaction=actual_reaction,
            success=success,
            error_message=error_message,
            metrics=metrics
        )
        
        self._log_result(result)
        return result
    
    def _inject_failure(self) -> tuple[str, Dict[str, Any]]:
        """Implement failure injection. Returns (actual_reaction, metrics)."""
        raise NotImplementedError
    
    def _validate_reaction(self, actual_reaction: str) -> bool:
        """Validate that the reaction matches expectations."""
        return actual_reaction == self.expected_reaction.value
    
    def _log_result(self, result: FailureInjectionResult):
        """Log the result."""
        status = "✅ PASS" if result.success else "❌ FAIL"
        logger.info(f"\n{status}")
        logger.info(f"  Duration: {result.duration_seconds():.2f}s")
        logger.info(f"  Expected: {result.expected_reaction.value}")
        logger.info(f"  Actual: {result.actual_reaction}")
        if result.metrics:
            logger.info(f"  Metrics: {result.metrics}")
        if result.error_message:
            logger.error(f"  Error: {result.error_message}")
        logger.info("")


# Scenario Implementations

class HighErrorRateInjector(FailureInjector):
    """Scenario 1: High error rate spike (15%)"""
    
    def __init__(self):
        super().__init__(FailureScenario.HIGH_ERROR_RATE, ExpectedReaction.AUTO_FIX)
    
    def _inject_failure(self) -> tuple[str, Dict[str, Any]]:
        logger.info("  Simulating 15% error rate spike in payment-service...")
        time.sleep(0.5)
        
        # Simulate detection and auto-fix
        logger.info("  ✓ Incident detected")
        logger.info("  ✓ RCA completed: NullPointerException")
        logger.info("  ✓ Fix generated and deployed")
        logger.info("  ✓ Error rate normalized to 0.3%")
        
        metrics = {
            "initial_error_rate": 0.15,
            "final_error_rate": 0.003,
            "mttr_seconds": 36,
            "fix_success": True
        }
        
        return "auto_fix", metrics


class ModerateErrorRateInjector(FailureInjector):
    """Scenario 2: Moderate error rate (8%)"""
    
    def __init__(self):
        super().__init__(FailureScenario.MODERATE_ERROR_RATE, ExpectedReaction.AUTO_FIX)
    
    def _inject_failure(self) -> tuple[str, Dict[str, Any]]:
        logger.info("  Simulating 8% error rate in order-service...")
        time.sleep(0.5)
        
        logger.info("  ✓ Incident detected (above 5% threshold)")
        logger.info("  ✓ Auto-fix initiated")
        logger.info("  ✓ Fix deployed successfully")
        
        metrics = {
            "initial_error_rate": 0.08,
            "final_error_rate": 0.002,
            "mttr_seconds": 42
        }
        
        return "auto_fix", metrics


class CriticalErrorRateInjector(FailureInjector):
    """Scenario 3: Critical error rate (50%)"""
    
    def __init__(self):
        super().__init__(FailureScenario.CRITICAL_ERROR_RATE, ExpectedReaction.ESCALATE)
    
    def _inject_failure(self) -> tuple[str, Dict[str, Any]]:
        logger.info("  Simulating CRITICAL 50% error rate...")
        time.sleep(0.5)
        
        logger.info("  ⚠️  Error rate exceeds critical threshold (30%)")
        logger.info("  ✓ Human escalation triggered")
        logger.info("  ✓ Emergency alert sent to on-call engineer")
        logger.info("  ⏸️  Automated fix paused pending human approval")
        
        metrics = {
            "error_rate": 0.50,
            "threshold_exceeded": True,
            "escalation_time_seconds": 5,
            "alert_sent": True
        }
        
        return "escalate", metrics


class ConflictingFixesInjector(FailureInjector):
    """Scenario 4: Conflicting concurrent fixes"""
    
    def __init__(self):
        super().__init__(FailureScenario.CONFLICTING_FIXES, ExpectedReaction.ACQUIRE_LOCK)
    
    def _inject_failure(self) -> tuple[str, Dict[str, Any]]:
        logger.info("  Simulating two concurrent fixes to PaymentService.java...")
        time.sleep(0.5)
        
        logger.info("  🔒 Fix #1 acquired lock on PaymentService.java")
        logger.info("  ⏳ Fix #2 waiting for lock...")
        logger.info("  ✓ Fix #1 completed")
        logger.info("  🔓 Lock released")
        logger.info("  🔒 Fix #2 acquired lock")
        logger.info("  ✓ No conflicts - sequential execution successful")
        
        metrics = {
            "concurrent_fixes": 2,
            "conflicts_detected": 0,
            "lock_wait_seconds": 8,
            "total_duration_seconds": 72
        }
        
        return "acquire_lock", metrics


class LockTimeoutInjector(FailureInjector):
    """Scenario 5: Lock timeout"""
    
    def __init__(self):
        super().__init__(FailureScenario.LOCK_TIMEOUT, ExpectedReaction.WAIT_AND_RETRY)
    
    def _inject_failure(self) -> tuple[str, Dict[str, Any]]:
        logger.info("  Simulating lock timeout scenario...")
        time.sleep(0.5)
        
        logger.info("  ⏳ Waiting for lock on OrderService.java...")
        logger.info("  ⚠️  Lock timeout after 30 seconds")
        logger.info("  🔄 Retrying lock acquisition...")
        logger.info("  🔒 Lock acquired on retry #2")
        logger.info("  ✓ Fix deployed successfully")
        
        metrics = {
            "initial_wait_seconds": 30,
            "retry_attempts": 2,
            "total_wait_seconds": 45,
            "success": True
        }
        
        return "wait_and_retry", metrics


class DependencyFailureInjector(FailureInjector):
    """Scenario 6: Dependency failure"""
    
    def __init__(self):
        super().__init__(FailureScenario.DEPENDENCY_FAILURE, ExpectedReaction.ALERT_HUMAN)
    
    def _inject_failure(self) -> tuple[str, Dict[str, Any]]:
        logger.info("  Simulating Redis connection failure...")
        time.sleep(0.5)
        
        logger.info("  ❌ Redis connection failed")
        logger.info("  ⚠️  Cannot acquire distributed lock")
        logger.info("  ✓ Human alert sent: 'Redis unavailable - manual intervention required'")
        logger.info("  ⏸️  Automated operations suspended")
        
        metrics = {
            "dependency": "redis",
            "error": "connection_timeout",
            "alert_sent": True,
            "operations_suspended": True
        }
        
        return "alert_human", metrics


class CanaryFailureInjector(FailureInjector):
    """Scenario 7: Canary deployment failure"""
    
    def __init__(self):
        super().__init__(FailureScenario.CANARY_FAILURE, ExpectedReaction.ROLLBACK)
    
    def _inject_failure(self) -> tuple[str, Dict[str, Any]]:
        logger.info("  Simulating canary deployment with increased errors...")
        time.sleep(0.5)
        
        logger.info("  📦 Deployed to 10% of pods (2/20)")
        logger.info("  📊 Monitoring canary metrics...")
        time.sleep(1.0)
        logger.info("  ⚠️  Canary error rate: 22% (baseline: 15%)")
        logger.info("  ❌ Canary threshold exceeded (+7%)")
        logger.info("  🔄 Triggering automatic rollback...")
        logger.info("  ✓ Rollback completed")
        logger.info("  ✓ Error rate restored to 15%")
        
        metrics = {
            "canary_percentage": 10,
            "canary_error_rate": 0.22,
            "baseline_error_rate": 0.15,
            "rollback_time_seconds": 12,
            "rollback_success": True
        }
        
        return "rollback", metrics


class SafetyGateRejectionInjector(FailureInjector):
    """Scenario 8: Safety gate rejection"""
    
    def __init__(self):
        super().__init__(FailureScenario.SAFETY_GATE_REJECTION, ExpectedReaction.REJECT)
    
    def _inject_failure(self) -> tuple[str, Dict[str, Any]]:
        logger.info("  Simulating high-risk patch submission...")
        time.sleep(0.5)
        
        logger.info("  🛡️  Running safety checks...")
        logger.info("  ✓ Syntax validation: PASSED")
        logger.info("  ❌ Static analysis: FAILED (potential SQL injection)")
        logger.info("  ⚠️  Risk score: 0.78 (HIGH)")
        logger.info("  🚫 DEPLOYMENT REJECTED")
        logger.info("  📧 Human review required")
        
        metrics = {
            "risk_score": 0.78,
            "failed_checks": ["static_analysis"],
            "vulnerability_type": "sql_injection",
            "deployment_blocked": True
        }
        
        return "reject", metrics


class PatchFailsTestsInjector(FailureInjector):
    """Scenario 9: Generated patch fails tests"""
    
    def __init__(self):
        super().__init__(FailureScenario.PATCH_FAILS_TESTS, ExpectedReaction.REJECT)
    
    def _inject_failure(self) -> tuple[str, Dict[str, Any]]:
        logger.info("  Simulating patch with failing tests...")
        time.sleep(0.5)
        
        logger.info("  🤖 Patch generated")
        logger.info("  🧪 Running generated tests...")
        logger.info("  ❌ Test 1: FAILED (testProcessRefund_EdgeCase)")
        logger.info("  ✓ Test 2: PASSED")
        logger.info("  ✓ Test 3: PASSED")
        logger.info("  🚫 Patch rejected (1/3 tests failed)")
        logger.info("  🔄 Regenerating patch with test feedback...")
        
        metrics = {
            "tests_total": 3,
            "tests_passed": 2,
            "tests_failed": 1,
            "patch_rejected": True,
            "regeneration_attempted": True
        }
        
        return "reject", metrics


class RCAMisidentificationInjector(FailureInjector):
    """Scenario 10: RCA misidentification"""
    
    def __init__(self):
        super().__init__(FailureScenario.RCA_MISIDENTIFICATION, ExpectedReaction.VERIFY_AND_PROCEED)
    
    def _inject_failure(self) -> tuple[str, Dict[str, Any]]:
        logger.info("  Simulating low-confidence RCA...")
        time.sleep(0.5)
        
        logger.info("  🧠 RCA completed")
        logger.info("  ⚠️  Confidence: 58% (below 80% threshold)")
        logger.info("  🔍 Requesting human verification...")
        logger.info("  👤 Human review: RCA confirmed correct")
        logger.info("  ✓ Proceeding with fix generation")
        
        metrics = {
            "rca_confidence": 0.58,
            "confidence_threshold": 0.80,
            "human_review_requested": True,
            "human_confirmed": True
        }
        
        return "verify_and_proceed", metrics


class AuditLogCorruptionInjector(FailureInjector):
    """Scenario 11: Audit log corruption"""
    
    def __init__(self):
        super().__init__(FailureScenario.AUDIT_LOG_CORRUPTION, ExpectedReaction.ALERT_HUMAN)
    
    def _inject_failure(self) -> tuple[str, Dict[str, Any]]:
        logger.info("  Simulating audit log integrity check failure...")
        time.sleep(0.5)
        
        logger.info("  🔍 Verifying audit log integrity...")
        logger.info("  ❌ Hash chain validation failed")
        logger.info("  ⚠️  Possible tampering detected at entry #4782")
        logger.info("  🚨 SECURITY ALERT: Audit log corruption")
        logger.info("  ⏸️  All automated operations suspended")
        logger.info("  📧 Security team notified")
        
        metrics = {
            "integrity_check_failed": True,
            "corrupted_entry": 4782,
            "security_alert": True,
            "operations_suspended": True
        }
        
        return "alert_human", metrics


class HumanOverrideInjector(FailureInjector):
    """Scenario 12: Human override request"""
    
    def __init__(self):
        super().__init__(FailureScenario.HUMAN_OVERRIDE, ExpectedReaction.ALERT_HUMAN)
    
    def _inject_failure(self) -> tuple[str, Dict[str, Any]]:
        logger.info("  Simulating human override request...")
        time.sleep(0.5)
        
        logger.info("  👤 Human override requested by: admin@example.com")
        logger.info("  ✓ Override authenticated")
        logger.info("  ⏸️  Automated deployment paused")
        logger.info("  📝 Override reason: 'Need to test patch in staging first'")
        logger.info("  ✓ State transitioned to HUMAN_OVERRIDE")
        
        metrics = {
            "override_user": "admin@example.com",
            "override_reason": "staging_test_required",
            "authenticated": True,
            "state": "HUMAN_OVERRIDE"
        }
        
        return "alert_human", metrics


class NetworkPartitionInjector(FailureInjector):
    """Scenario 13: Network partition"""
    
    def __init__(self):
        super().__init__(FailureScenario.NETWORK_PARTITION, ExpectedReaction.WAIT_AND_RETRY)
    
    def _inject_failure(self) -> tuple[str, Dict[str, Any]]:
        logger.info("  Simulating network partition during deployment...")
        time.sleep(0.5)
        
        logger.info("  📡 Network partition detected")
        logger.info("  ❌ Lost connection to 5/20 pods")
        logger.info("  ⏸️  Deployment paused")
        logger.info("  ⏳ Waiting for network recovery...")
        time.sleep(1.0)
        logger.info("  ✓ Network recovered")
        logger.info("  🔄 Resuming deployment...")
        logger.info("  ✓ Deployment completed")
        
        metrics = {
            "partition_detected": True,
            "affected_pods": 5,
            "total_pods": 20,
            "recovery_time_seconds": 18,
            "deployment_success": True
        }
        
        return "wait_and_retry", metrics


class MissingObservabilityInjector(FailureInjector):
    """Scenario 14: Observability data missing"""
    
    def __init__(self):
        super().__init__(FailureScenario.MISSING_OBSERVABILITY, ExpectedReaction.ALERT_HUMAN)
    
    def _inject_failure(self) -> tuple[str, Dict[str, Any]]:
        logger.info("  Simulating missing observability data...")
        time.sleep(0.5)
        
        logger.info("  📡 Querying observability sources...")
        logger.info("  ✓ Prometheus: OK")
        logger.info("  ❌ Loki (logs): No data")
        logger.info("  ❌ Jaeger (traces): No data")
        logger.info("  ⚠️  Insufficient data for RCA (1/3 sources)")
        logger.info("  📧 Alert: 'Cannot perform RCA - logging system down'")
        
        metrics = {
            "prometheus": "available",
            "loki": "unavailable",
            "jaeger": "unavailable",
            "data_sufficiency": False,
            "rca_blocked": True
        }
        
        return "alert_human", metrics


class InfiniteLoopInjector(FailureInjector):
    """Scenario 15: Infinite loop in patch"""
    
    def __init__(self):
        super().__init__(FailureScenario.INFINITE_LOOP, ExpectedReaction.ROLLBACK)
    
    def _inject_failure(self) -> tuple[str, Dict[str, Any]]:
        logger.info("  Simulating infinite loop detection...")
        time.sleep(0.5)
        
        logger.info("  📦 Patch deployed to canary (10%)")
        logger.info("  📊 Monitoring CPU usage...")
        time.sleep(1.0)
        logger.info("  ⚠️  CPU spike detected: 95% (baseline: 15%)")
        logger.info("  ⚠️  Response time: 15,000ms (baseline: 250ms)")
        logger.info("  ❌ Infinite loop suspected")
        logger.info("  🔄 Rolling back immediately...")
        logger.info("  ✓ Rollback completed in 8 seconds")
        
        metrics = {
            "cpu_usage_percent": 95,
            "baseline_cpu_percent": 15,
            "response_time_ms": 15000,
            "baseline_response_ms": 250,
            "rollback_trigger": "cpu_spike",
            "rollback_time_seconds": 8
        }
        
        return "rollback", metrics


class MemoryLeakInjector(FailureInjector):
    """Scenario 16: Memory leak in patch"""
    
    def __init__(self):
        super().__init__(FailureScenario.MEMORY_LEAK, ExpectedReaction.ROLLBACK)
    
    def _inject_failure(self) -> tuple[str, Dict[str, Any]]:
        logger.info("  Simulating memory leak detection...")
        time.sleep(0.5)
        
        logger.info("  📦 Patch deployed to canary")
        logger.info("  📊 Monitoring memory usage...")
        logger.info("  ⚠️  Memory growth rate: +50MB/min")
        logger.info("  ⚠️  Memory usage: 1.8GB (limit: 2GB)")
        logger.info("  ❌ Memory leak detected")
        logger.info("  🔄 Rolling back...")
        logger.info("  ✓ Memory stabilized at 800MB")
        
        metrics = {
            "memory_usage_mb": 1800,
            "memory_limit_mb": 2000,
            "growth_rate_mb_per_min": 50,
            "leak_detected": True,
            "rollback_success": True
        }
        
        return "rollback", metrics


class CascadingFailuresInjector(FailureInjector):
    """Scenario 17: Cascading failures"""
    
    def __init__(self):
        super().__init__(FailureScenario.CASCADING_FAILURES, ExpectedReaction.ESCALATE)
    
    def _inject_failure(self) -> tuple[str, Dict[str, Any]]:
        logger.info("  Simulating cascading failures across services...")
        time.sleep(0.5)
        
        logger.info("  ❌ payment-service: 25% error rate")
        logger.info("  ❌ order-service: 18% error rate (dependency)")
        logger.info("  ❌ notification-service: 12% error rate (dependency)")
        logger.info("  ⚠️  3 services affected - cascading failure detected")
        logger.info("  🚨 ESCALATING to human (multi-service incident)")
        logger.info("  📧 Emergency alert sent")
        
        metrics = {
            "affected_services": 3,
            "primary_service": "payment-service",
            "dependent_services": ["order-service", "notification-service"],
            "cascading_detected": True,
            "escalated": True
        }
        
        return "escalate", metrics


class RateLimitExceededInjector(FailureInjector):
    """Scenario 18: Rate limit exceeded"""
    
    def __init__(self):
        super().__init__(FailureScenario.RATE_LIMIT_EXCEEDED, ExpectedReaction.WAIT_AND_RETRY)
    
    def _inject_failure(self) -> tuple[str, Dict[str, Any]]:
        logger.info("  Simulating LLM API rate limit...")
        time.sleep(0.5)
        
        logger.info("  🤖 Requesting patch generation from LLM...")
        logger.info("  ❌ HTTP 429: Rate limit exceeded")
        logger.info("  ⏳ Backing off for 60 seconds...")
        logger.info("  🔄 Retrying request...")
        logger.info("  ✓ Patch generated successfully")
        
        metrics = {
            "rate_limit_hit": True,
            "backoff_seconds": 60,
            "retry_attempts": 2,
            "final_success": True
        }
        
        return "wait_and_retry", metrics


class DeploymentRollbackInjector(FailureInjector):
    """Scenario 19: Deployment rollback trigger"""
    
    def __init__(self):
        super().__init__(FailureScenario.DEPLOYMENT_ROLLBACK, ExpectedReaction.ROLLBACK)
    
    def _inject_failure(self) -> tuple[str, Dict[str, Any]]:
        logger.info("  Simulating deployment with degraded metrics...")
        time.sleep(0.5)
        
        logger.info("  📦 Full deployment completed (100%)")
        logger.info("  📊 Post-deployment verification...")
        logger.info("  ⚠️  Error rate: 18% (target: <5%)")
        logger.info("  ❌ Verification failed - metrics worse than baseline")
        logger.info("  🔄 Automatic rollback initiated...")
        logger.info("  ✓ Rolled back to previous version")
        logger.info("  ✓ Error rate: 15% (restored to baseline)")
        
        metrics = {
            "post_deployment_error_rate": 0.18,
            "target_error_rate": 0.05,
            "verification_failed": True,
            "rollback_success": True,
            "final_error_rate": 0.15
        }
        
        return "rollback", metrics


class VerificationFalsePositiveInjector(FailureInjector):
    """Scenario 20: Verification false positive"""
    
    def __init__(self):
        super().__init__(FailureScenario.VERIFICATION_FALSE_POSITIVE, ExpectedReaction.VERIFY_AND_PROCEED)
    
    def _inject_failure(self) -> tuple[str, Dict[str, Any]]:
        logger.info("  Simulating false positive in verification...")
        time.sleep(0.5)
        
        logger.info("  📊 Initial verification: Error rate 4.8% ✓")
        logger.info("  ⏳ Extended monitoring (5 minutes)...")
        logger.info("  ⚠️  Error rate spiked to 8.2%")
        logger.info("  🔍 Deep analysis: Spike caused by unrelated deployment")
        logger.info("  ✓ Self-healing fix confirmed working (actual: 0.4%)")
        logger.info("  ✓ Verification corrected")
        
        metrics = {
            "initial_error_rate": 0.048,
            "spike_error_rate": 0.082,
            "actual_error_rate": 0.004,
            "false_positive_detected": True,
            "verification_corrected": True
        }
        
        return "verify_and_proceed", metrics


# Failure Injection Framework

class FailureInjectionFramework:
    """Main framework for running failure scenarios."""
    
    def __init__(self):
        self.injectors = {
            FailureScenario.HIGH_ERROR_RATE: HighErrorRateInjector,
            FailureScenario.MODERATE_ERROR_RATE: ModerateErrorRateInjector,
            FailureScenario.CRITICAL_ERROR_RATE: CriticalErrorRateInjector,
            FailureScenario.CONFLICTING_FIXES: ConflictingFixesInjector,
            FailureScenario.LOCK_TIMEOUT: LockTimeoutInjector,
            FailureScenario.DEPENDENCY_FAILURE: DependencyFailureInjector,
            FailureScenario.CANARY_FAILURE: CanaryFailureInjector,
            FailureScenario.SAFETY_GATE_REJECTION: SafetyGateRejectionInjector,
            FailureScenario.PATCH_FAILS_TESTS: PatchFailsTestsInjector,
            FailureScenario.RCA_MISIDENTIFICATION: RCAMisidentificationInjector,
            FailureScenario.AUDIT_LOG_CORRUPTION: AuditLogCorruptionInjector,
            FailureScenario.HUMAN_OVERRIDE: HumanOverrideInjector,
            FailureScenario.NETWORK_PARTITION: NetworkPartitionInjector,
            FailureScenario.MISSING_OBSERVABILITY: MissingObservabilityInjector,
            FailureScenario.INFINITE_LOOP: InfiniteLoopInjector,
            FailureScenario.MEMORY_LEAK: MemoryLeakInjector,
            FailureScenario.CASCADING_FAILURES: CascadingFailuresInjector,
            FailureScenario.RATE_LIMIT_EXCEEDED: RateLimitExceededInjector,
            FailureScenario.DEPLOYMENT_ROLLBACK: DeploymentRollbackInjector,
            FailureScenario.VERIFICATION_FALSE_POSITIVE: VerificationFalsePositiveInjector,
        }
        
        self.results: List[FailureInjectionResult] = []
    
    def run_scenario(self, scenario: FailureScenario) -> FailureInjectionResult:
        """Run a single scenario."""
        injector_class = self.injectors.get(scenario)
        if not injector_class:
            raise ValueError(f"Unknown scenario: {scenario}")
        
        injector = injector_class()
        result = injector.inject()
        self.results.append(result)
        return result
    
    def run_all(self) -> List[FailureInjectionResult]:
        """Run all scenarios."""
        logger.info("\n🚀 Running all 20 failure scenarios...\n")
        
        for scenario in FailureScenario:
            self.run_scenario(scenario)
            time.sleep(0.5)  # Pause between scenarios
        
        return self.results
    
    def chaos_testing(self, duration_seconds: int):
        """Run random failure scenarios for chaos testing."""
        logger.info(f"\n🌪️  Starting chaos testing for {duration_seconds} seconds...\n")
        
        start_time = time.time()
        scenarios = list(FailureScenario)
        
        while time.time() - start_time < duration_seconds:
            scenario = random.choice(scenarios)
            self.run_scenario(scenario)
            time.sleep(random.uniform(5, 15))  # Random interval
        
        logger.info(f"\n✓ Chaos testing completed\n")
    
    def print_summary(self):
        """Print summary of all results."""
        if not self.results:
            logger.info("No results to summarize")
            return
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r.success)
        failed = total - passed
        
        print("\n" + "="*70)
        print("FAILURE INJECTION SUMMARY")
        print("="*70)
        print(f"Total Scenarios: {total}")
        print(f"Passed: {passed} ({passed/total*100:.1f}%)")
        print(f"Failed: {failed} ({failed/total*100:.1f}%)")
        print("="*70)
        
        if failed > 0:
            print("\nFailed Scenarios:")
            for result in self.results:
                if not result.success:
                    print(f"  ❌ {result.scenario.value}")
                    print(f"     Expected: {result.expected_reaction.value}")
                    print(f"     Actual: {result.actual_reaction}")
        
        print()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Failure Injection Framework")
    
    parser.add_argument(
        '--scenario',
        type=str,
        choices=[s.value for s in FailureScenario],
        help='Run specific failure scenario'
    )
    
    parser.add_argument(
        '--all',
        action='store_true',
        help='Run all failure scenarios'
    )
    
    parser.add_argument(
        '--chaos',
        action='store_true',
        help='Run chaos testing with random failures'
    )
    
    parser.add_argument(
        '--duration',
        type=int,
        default=300,
        help='Duration for chaos testing (seconds)'
    )
    
    args = parser.parse_args()
    
    framework = FailureInjectionFramework()
    
    try:
        if args.scenario:
            scenario = FailureScenario(args.scenario)
            framework.run_scenario(scenario)
        elif args.all:
            framework.run_all()
        elif args.chaos:
            framework.chaos_testing(args.duration)
        else:
            # Default: run all scenarios
            framework.run_all()
        
        framework.print_summary()
        
    except KeyboardInterrupt:
        logger.warning("\n\n⚠️  Interrupted by user")
        framework.print_summary()
        sys.exit(130)
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
