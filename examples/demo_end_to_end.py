#!/usr/bin/env python3
"""
End-to-End Self-Healing System Demo
=====================================

Demonstrates the complete self-healing workflow with the payment service null pointer scenario.
Timeline: 36 seconds from detection to verification.

Scenario: Payment service null pointer error (15% error rate → 0.3%)
MTTR: Manual (45 minutes) → Automated (36 seconds) = 75x improvement

Usage:
    python demo_end_to_end.py [--inject-failure TYPE] [--verbose]

Options:
    --inject-failure TYPE    Inject specific failure type (see failure_injection.py)
    --verbose               Show detailed step execution
    --realtime              Execute with realistic timing delays
    --fast                  Execute with minimal delays (default)
"""

import sys
import os
import time
import json
import logging
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class DemoPhase(Enum):
    """Phases in the demo execution."""
    SETUP = "setup"
    DETECTION = "detection"
    OBSERVABILITY = "observability"
    RCA = "rca"
    LOCALIZATION = "localization"
    FIX_PLANNING = "fix_planning"
    PATCH_GENERATION = "patch_generation"
    SAFETY_GATES = "safety_gates"
    DEPLOYMENT = "deployment"
    VERIFICATION = "verification"
    COMPLETED = "completed"


@dataclass
class TimingMetrics:
    """Tracks timing for each phase."""
    start_time: float = field(default_factory=time.time)
    phase_timings: Dict[str, float] = field(default_factory=dict)
    phase_starts: Dict[str, float] = field(default_factory=dict)
    
    def start_phase(self, phase: DemoPhase):
        """Start timing a phase."""
        self.phase_starts[phase.value] = time.time()
    
    def end_phase(self, phase: DemoPhase):
        """End timing a phase."""
        if phase.value in self.phase_starts:
            elapsed = time.time() - self.phase_starts[phase.value]
            self.phase_timings[phase.value] = elapsed
    
    def total_elapsed(self) -> float:
        """Get total elapsed time."""
        return time.time() - self.start_time
    
    def get_summary(self) -> Dict[str, Any]:
        """Get timing summary."""
        return {
            "total_seconds": round(self.total_elapsed(), 2),
            "phase_breakdown": {
                phase: round(duration, 2) 
                for phase, duration in self.phase_timings.items()
            }
        }


@dataclass
class IncidentContext:
    """Represents an incident being processed."""
    incident_id: str
    service_name: str
    error_type: str
    error_rate: float
    timestamp: datetime = field(default_factory=datetime.now)
    status: str = "detected"
    
    # RCA findings
    root_cause: Optional[str] = None
    stack_trace: Optional[List[str]] = None
    affected_files: Optional[List[str]] = None
    
    # Fix information
    patch_code: Optional[str] = None
    confidence_score: Optional[float] = None
    risk_score: Optional[float] = None
    
    # Deployment info
    canary_percentage: Optional[int] = None
    deployment_id: Optional[str] = None
    
    # Verification
    post_error_rate: Optional[float] = None
    verification_status: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


class DemoStep:
    """Base class for demo steps."""
    
    def __init__(self, name: str, step_number: int, timing_budget: float):
        self.name = name
        self.step_number = step_number
        self.timing_budget = timing_budget
        
    def execute(self, context: IncidentContext, verbose: bool = False) -> bool:
        """Execute the step. Returns True if successful."""
        raise NotImplementedError


class Step1_IncidentDetection(DemoStep):
    """Step 1: Incident Detection (2 seconds)"""
    
    def __init__(self):
        super().__init__("Incident Detection", 1, 2.0)
        
    def execute(self, context: IncidentContext, verbose: bool = False) -> bool:
        logger.info(f"[Step {self.step_number}] {self.name}")
        logger.info(f"  🔍 Monitoring payment-service (port 8080)")
        
        # Simulate detection delay
        time.sleep(0.3)
        
        logger.warning(f"  ⚠️  HIGH ERROR RATE DETECTED: {context.error_rate*100:.1f}%")
        logger.info(f"  📊 Baseline: 0.3% | Current: {context.error_rate*100:.1f}% | Threshold: 5%")
        logger.info(f"  🆔 Incident ID: {context.incident_id}")
        
        if verbose:
            logger.info(f"  📈 Error spike detected at {context.timestamp.strftime('%H:%M:%S')}")
            logger.info(f"  🎯 Severity: HIGH (threshold exceeded by {context.error_rate*100 - 5:.1f}%)")
        
        context.status = "analyzing"
        return True


class Step2_ObservabilityData(DemoStep):
    """Step 2: Observability Data Collection (2 seconds)"""
    
    def __init__(self):
        super().__init__("Observability Data Collection", 2, 2.0)
        
    def execute(self, context: IncidentContext, verbose: bool = False) -> bool:
        logger.info(f"[Step {self.step_number}] {self.name}")
        logger.info(f"  📡 Querying Prometheus, Loki, Jaeger...")
        
        time.sleep(0.4)
        
        # Simulate data collection
        context.stack_trace = [
            "java.lang.NullPointerException",
            "  at com.example.payment.PaymentService.processRefund(PaymentService.java:237)",
            "  at com.example.payment.RefundController.handleRefund(RefundController.java:89)",
            "  at jdk.internal.reflect.NativeMethodAccessorImpl.invoke0(Native Method)"
        ]
        
        logger.info(f"  ✓ Metrics: 847 error samples in last 5 minutes")
        logger.info(f"  ✓ Logs: NullPointerException in PaymentService.processRefund()")
        logger.info(f"  ✓ Traces: 15.2% of spans failing with 500 status")
        
        if verbose:
            logger.info(f"  📊 Collected 3 data sources (metrics, logs, traces)")
            logger.info(f"  🔗 Correlated by trace_id and service_name")
            for line in context.stack_trace[:2]:
                logger.info(f"     {line}")
        
        return True


class Step3_RootCauseAnalysis(DemoStep):
    """Step 3: Root Cause Analysis (4 seconds)"""
    
    def __init__(self):
        super().__init__("Root Cause Analysis", 3, 4.0)
        
    def execute(self, context: IncidentContext, verbose: bool = False) -> bool:
        logger.info(f"[Step {self.step_number}] {self.name}")
        logger.info(f"  🧠 Analyzing error patterns with Neo4j dependency graph...")
        
        time.sleep(0.5)
        
        # Simulate RCA
        context.root_cause = "Missing null check for 'customer.preferredPaymentMethod' in refund flow"
        context.affected_files = ["src/main/java/com/example/payment/PaymentService.java"]
        
        logger.info(f"  🎯 ROOT CAUSE IDENTIFIED:")
        logger.info(f"     File: PaymentService.java:237")
        logger.info(f"     Issue: {context.root_cause}")
        logger.info(f"  📊 Confidence: 94% (based on 847 error samples)")
        
        if verbose:
            logger.info(f"  🔍 Analysis method: Pattern matching + dependency tracing")
            logger.info(f"  🔗 Upstream: RefundController → PaymentService")
            logger.info(f"  📝 No recent deployments or config changes detected")
        
        return True


class Step4_CodeLocalization(DemoStep):
    """Step 4: Code Localization (2 seconds)"""
    
    def __init__(self):
        super().__init__("Code Localization", 4, 2.0)
        
    def execute(self, context: IncidentContext, verbose: bool = False) -> bool:
        logger.info(f"[Step {self.step_number}] {self.name}")
        logger.info(f"  🔎 Localizing fault in source code...")
        
        time.sleep(0.3)
        
        logger.info(f"  📍 Fault Location:")
        logger.info(f"     Line 237: PaymentMethod method = customer.preferredPaymentMethod.get(refund.type);")
        logger.info(f"     Issue: 'preferredPaymentMethod' is null for 15% of customers")
        logger.info(f"  ✓ Surrounding context extracted (±10 lines)")
        
        if verbose:
            logger.info(f"  📂 Repository: /services/payment-service")
            logger.info(f"  🌳 Branch: main (commit: a7f3b9c)")
            logger.info(f"  📊 Lines of context: 21 (line 227-247)")
        
        return True


class Step5_FixPlanning(DemoStep):
    """Step 5: Fix Planning (3 seconds)"""
    
    def __init__(self):
        super().__init__("Fix Planning", 5, 3.0)
        
    def execute(self, context: IncidentContext, verbose: bool = False) -> bool:
        logger.info(f"[Step {self.step_number}] {self.name}")
        logger.info(f"  🛠️  Generating fix strategy...")
        
        time.sleep(0.4)
        
        logger.info(f"  📋 FIX PLAN:")
        logger.info(f"     Strategy: Add null-safety guard with fallback")
        logger.info(f"     Approach: Defensive null check + default payment method")
        logger.info(f"     Impact: Single method (processRefund)")
        logger.info(f"     Risk Level: LOW (localized change, no dependencies)")
        
        if verbose:
            logger.info(f"  🎯 Alternative strategies considered:")
            logger.info(f"     1. Null check (chosen - safest)")
            logger.info(f"     2. Optional<> wrapper (refactor required)")
            logger.info(f"     3. Database fix (out of scope)")
        
        return True


class Step6_PatchGeneration(DemoStep):
    """Step 6: Patch Generation (5 seconds)"""
    
    def __init__(self):
        super().__init__("Patch Generation", 6, 5.0)
        
    def execute(self, context: IncidentContext, verbose: bool = False) -> bool:
        logger.info(f"[Step {self.step_number}] {self.name}")
        logger.info(f"  🤖 Generating code patch with LLM...")
        
        time.sleep(0.6)
        
        # Simulate patch generation
        context.patch_code = """
// BEFORE (line 237):
PaymentMethod method = customer.preferredPaymentMethod.get(refund.type);

// AFTER (line 237-241):
PaymentMethod method = null;
if (customer.preferredPaymentMethod != null) {
    method = customer.preferredPaymentMethod.get(refund.type);
}
method = (method != null) ? method : PaymentMethod.DEFAULT;
"""
        
        context.confidence_score = 0.92
        
        logger.info(f"  ✓ PATCH GENERATED:")
        logger.info(f"     Lines changed: 1 → 5")
        logger.info(f"     Added: Null check + fallback to PaymentMethod.DEFAULT")
        logger.info(f"     Confidence: {context.confidence_score*100:.0f}%")
        logger.info(f"  🧪 Static analysis: PASSED (no new warnings)")
        
        if verbose:
            logger.info(f"  📝 Patch details:")
            for line in context.patch_code.strip().split('\n')[:4]:
                logger.info(f"     {line}")
            logger.info(f"     ... ({len(context.patch_code.split(chr(10)))} lines total)")
        
        return True


class Step7_SafetyGates(DemoStep):
    """Step 7: Safety Gates (3 seconds)"""
    
    def __init__(self):
        super().__init__("Safety Gates", 7, 3.0)
        
    def execute(self, context: IncidentContext, verbose: bool = False) -> bool:
        logger.info(f"[Step {self.step_number}] {self.name}")
        logger.info(f"  🛡️  Running pre-deployment safety checks...")
        
        time.sleep(0.4)
        
        # Simulate safety checks
        context.risk_score = 0.18  # Low risk
        
        logger.info(f"  ✅ Syntax validation: PASSED")
        logger.info(f"  ✅ Unit test generation: 3 tests created & passed")
        logger.info(f"  ✅ Static analysis: No new vulnerabilities")
        logger.info(f"  ✅ Dependency check: No impact on downstream services")
        logger.info(f"  📊 RISK SCORE: {context.risk_score:.2f}/1.0 (LOW) ✓")
        
        if verbose:
            logger.info(f"  🔍 Generated tests:")
            logger.info(f"     - testProcessRefund_NullPreferredPaymentMethod()")
            logger.info(f"     - testProcessRefund_ValidPaymentMethod()")
            logger.info(f"     - testProcessRefund_FallbackToDefault()")
        
        return True


class Step8_Deployment(DemoStep):
    """Step 8: Deployment (8 seconds - includes canary)"""
    
    def __init__(self):
        super().__init__("Deployment", 8, 8.0)
        
    def execute(self, context: IncidentContext, verbose: bool = False) -> bool:
        logger.info(f"[Step {self.step_number}] {self.name}")
        logger.info(f"  🚀 Initiating canary deployment...")
        
        context.deployment_id = f"deploy-{int(time.time())}"
        context.canary_percentage = 10
        
        # Phase 1: 10% canary
        logger.info(f"  📦 Phase 1: Deploying to 10% of pods (2/20 pods)...")
        time.sleep(0.5)
        logger.info(f"     ✓ Canary pods healthy (2/2)")
        logger.info(f"     ✓ Error rate: 15.0% → 13.5% (initial drop)")
        
        time.sleep(1.0)  # Canary observation
        
        # Phase 2: 50% rollout
        context.canary_percentage = 50
        logger.info(f"  📦 Phase 2: Expanding to 50% of pods (10/20 pods)...")
        time.sleep(0.5)
        logger.info(f"     ✓ All pods healthy (10/10)")
        logger.info(f"     ✓ Error rate: 13.5% → 7.8%")
        
        time.sleep(1.0)
        
        # Phase 3: 100% rollout
        context.canary_percentage = 100
        logger.info(f"  📦 Phase 3: Full rollout to 100% of pods (20/20 pods)...")
        time.sleep(0.5)
        logger.info(f"     ✓ All pods healthy (20/20)")
        logger.info(f"     ✓ Error rate: 7.8% → 0.3% ✓")
        
        if verbose:
            logger.info(f"  🔧 Deployment method: Kubernetes rolling update")
            logger.info(f"  🆔 Deployment ID: {context.deployment_id}")
            logger.info(f"  ⏱️  Total deployment time: ~8 seconds")
        
        return True


class Step9_Verification(DemoStep):
    """Step 9: Post-Deployment Verification (5 seconds)"""
    
    def __init__(self):
        super().__init__("Post-Deployment Verification", 9, 5.0)
        
    def execute(self, context: IncidentContext, verbose: bool = False) -> bool:
        logger.info(f"[Step {self.step_number}] {self.name}")
        logger.info(f"  🔬 Verifying fix effectiveness...")
        
        time.sleep(0.6)
        
        context.post_error_rate = 0.003  # 0.3%
        context.verification_status = "VERIFIED"
        
        logger.info(f"  ✅ ERROR RATE NORMALIZED:")
        logger.info(f"     Before: {context.error_rate*100:.1f}%")
        logger.info(f"     After:  {context.post_error_rate*100:.1f}%")
        logger.info(f"     Target: <5% ✓")
        logger.info(f"  ✅ No new errors introduced")
        logger.info(f"  ✅ Latency p99: 245ms (baseline: 250ms)")
        logger.info(f"  ✅ Throughput: 1,247 req/s (baseline: 1,250 req/s)")
        
        if verbose:
            logger.info(f"  📊 Verification metrics:")
            logger.info(f"     - Error rate: {context.post_error_rate*100:.2f}% (target: <5%)")
            logger.info(f"     - Response time: +2% (acceptable)")
            logger.info(f"     - Memory usage: +0.1% (negligible)")
            logger.info(f"     - CPU usage: -0.3% (improved)")
        
        logger.info(f"  🎉 INCIDENT RESOLVED: {context.incident_id}")
        context.status = "resolved"
        
        return True


class EndToEndDemo:
    """Orchestrates the complete end-to-end demo."""
    
    def __init__(self, realtime: bool = False, verbose: bool = False):
        self.realtime = realtime
        self.verbose = verbose
        self.metrics = TimingMetrics()
        
        # Initialize all steps
        self.steps: List[DemoStep] = [
            Step1_IncidentDetection(),
            Step2_ObservabilityData(),
            Step3_RootCauseAnalysis(),
            Step4_CodeLocalization(),
            Step5_FixPlanning(),
            Step6_PatchGeneration(),
            Step7_SafetyGates(),
            Step8_Deployment(),
            Step9_Verification(),
        ]
        
    def create_incident(self) -> IncidentContext:
        """Create the demo incident scenario."""
        timestamp = datetime.now()
        incident_id = f"INC-{timestamp.strftime('%Y%m%d')}-{int(timestamp.timestamp())}"
        
        return IncidentContext(
            incident_id=incident_id,
            service_name="payment-service",
            error_type="NullPointerException",
            error_rate=0.152,  # 15.2%
            timestamp=timestamp
        )
    
    def print_header(self):
        """Print demo header."""
        print("\n" + "="*80)
        print("  🤖 INTELLIGENT SELF-HEALING SYSTEM - END-TO-END DEMO")
        print("="*80)
        print(f"  Scenario: Payment Service Null Pointer Error")
        print(f"  Timeline: Complete detection → fix → deployment → verification")
        print(f"  Target MTTR: <36 seconds (vs 45 minutes manual)")
        print("="*80 + "\n")
    
    def print_footer(self, context: IncidentContext):
        """Print demo summary."""
        total_time = self.metrics.total_elapsed()
        
        print("\n" + "="*80)
        print("  📊 DEMO SUMMARY")
        print("="*80)
        print(f"  Incident ID: {context.incident_id}")
        print(f"  Service: {context.service_name}")
        print(f"  Status: {context.status.upper()}")
        print(f"  ")
        print(f"  ⏱️  TOTAL TIME: {total_time:.1f} seconds")
        print(f"  📉 Error Rate: {context.error_rate*100:.1f}% → {context.post_error_rate*100:.1f}%")
        print(f"  🎯 Improvement: {((context.error_rate - context.post_error_rate) / context.error_rate * 100):.1f}% reduction")
        print(f"  ")
        print(f"  ⚡ MTTR Comparison:")
        print(f"     Manual process: ~45 minutes (2,700 seconds)")
        print(f"     Automated: {total_time:.1f} seconds")
        print(f"     Improvement: {2700 / total_time:.0f}x faster")
        print("="*80)
        
        if self.verbose:
            print("\n  📈 Phase Breakdown:")
            for phase, duration in self.metrics.phase_timings.items():
                pct = (duration / total_time) * 100
                print(f"     {phase:25s}: {duration:5.2f}s ({pct:5.1f}%)")
        
        print("\n  ✅ Demo completed successfully!\n")
    
    def export_metrics(self, context: IncidentContext) -> Dict[str, Any]:
        """Export metrics for analysis."""
        return {
            "incident": context.to_dict(),
            "timing": self.metrics.get_summary(),
            "mttr_comparison": {
                "manual_seconds": 2700,
                "automated_seconds": round(self.metrics.total_elapsed(), 2),
                "improvement_factor": round(2700 / self.metrics.total_elapsed(), 2)
            },
            "error_rate_improvement": {
                "before": context.error_rate,
                "after": context.post_error_rate,
                "reduction_percent": round(
                    ((context.error_rate - context.post_error_rate) / context.error_rate) * 100, 
                    2
                )
            }
        }
    
    def run(self, inject_failure: Optional[str] = None) -> bool:
        """Run the complete demo."""
        self.print_header()
        
        # Create incident
        context = self.create_incident()
        logger.info(f"🎬 Starting demo at {context.timestamp.strftime('%H:%M:%S')}\n")
        
        # Execute each step
        phase_map = {
            0: DemoPhase.DETECTION,
            1: DemoPhase.OBSERVABILITY,
            2: DemoPhase.RCA,
            3: DemoPhase.LOCALIZATION,
            4: DemoPhase.FIX_PLANNING,
            5: DemoPhase.PATCH_GENERATION,
            6: DemoPhase.SAFETY_GATES,
            7: DemoPhase.DEPLOYMENT,
            8: DemoPhase.VERIFICATION,
        }
        
        for i, step in enumerate(self.steps):
            phase = phase_map[i]
            self.metrics.start_phase(phase)
            
            try:
                success = step.execute(context, verbose=self.verbose)
                if not success:
                    logger.error(f"❌ Step {step.step_number} failed!")
                    return False
                
                self.metrics.end_phase(phase)
                print()  # Blank line between steps
                
                # Add delay if realtime mode
                if self.realtime and i < len(self.steps) - 1:
                    time.sleep(0.5)
                    
            except Exception as e:
                logger.error(f"❌ Exception in Step {step.step_number}: {e}")
                return False
        
        # Print summary
        self.print_footer(context)
        
        # Export metrics
        metrics_file = "/tmp/demo_metrics.json"
        with open(metrics_file, 'w') as f:
            json.dump(self.export_metrics(context), f, indent=2)
        logger.info(f"📊 Metrics exported to {metrics_file}")
        
        return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="End-to-End Self-Healing System Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run demo with fast timing (default)
  python demo_end_to_end.py
  
  # Run with realistic delays
  python demo_end_to_end.py --realtime
  
  # Run with verbose output
  python demo_end_to_end.py --verbose
  
  # Run with failure injection
  python demo_end_to_end.py --inject-failure canary_failure --verbose
        """
    )
    
    parser.add_argument(
        '--inject-failure',
        type=str,
        help='Inject specific failure type (e.g., canary_failure, safety_gate_failure)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed step execution'
    )
    
    parser.add_argument(
        '--realtime',
        action='store_true',
        help='Execute with realistic timing delays'
    )
    
    parser.add_argument(
        '--fast',
        action='store_true',
        default=True,
        help='Execute with minimal delays (default)'
    )
    
    args = parser.parse_args()
    
    # Create and run demo
    demo = EndToEndDemo(
        realtime=args.realtime,
        verbose=args.verbose
    )
    
    try:
        success = demo.run(inject_failure=args.inject_failure)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.warning("\n\n⚠️  Demo interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"❌ Demo failed with exception: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
