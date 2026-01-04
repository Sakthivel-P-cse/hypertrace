#!/usr/bin/env python3
"""
Canary Controller for Step 8: Deployment Automation

Manages progressive canary rollout with metric-driven health gates.
Implements Google SRE best practices for safe deployments.
"""

import time
import subprocess
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from prometheus_metrics import PrometheusMetrics, HealthGateEvaluator, HealthGateResult
from deployment_state_machine import DeploymentStateMachine, DeploymentState


class CanaryStage(Enum):
    """Canary rollout stages"""
    STAGE_5 = 5
    STAGE_25 = 25
    STAGE_50 = 50
    STAGE_100 = 100


@dataclass
class CanaryConfig:
    """Configuration for canary rollout"""
    stages: List[int]  # e.g., [5, 25, 50, 100]
    wait_time_seconds: int  # Time to wait at each stage
    evaluation_window_seconds: int  # Window for metric evaluation
    max_failures: int  # Max health gate failures before rollback
    auto_promote: bool  # Auto-promote if all gates pass


@dataclass
class CanaryStageResult:
    """Result of a canary stage"""
    stage_percentage: int
    health_gate_result: HealthGateResult
    passed: bool
    timestamp: datetime
    duration_seconds: float


class CanaryController:
    """Controls canary rollout with progressive health gates"""
    
    def __init__(
        self,
        service_name: str,
        namespace: str = "default",
        prometheus_url: str = "http://localhost:9090",
        config: Optional[CanaryConfig] = None
    ):
        self.service_name = service_name
        self.namespace = namespace
        
        # Initialize Prometheus client
        self.prometheus = PrometheusMetrics(prometheus_url)
        self.evaluator = HealthGateEvaluator(self.prometheus)
        
        # Default canary configuration
        self.config = config or CanaryConfig(
            stages=[5, 25, 50, 100],
            wait_time_seconds=60,
            evaluation_window_seconds=300,
            max_failures=1,
            auto_promote=True
        )
    
    def execute_canary_rollout(
        self,
        new_version: str,
        baseline_version: str,
        state_machine: DeploymentStateMachine
    ) -> bool:
        """
        Execute full canary rollout with progressive health gates
        
        Args:
            new_version: New image version to deploy
            baseline_version: Current stable version
            state_machine: Deployment state machine for audit
        
        Returns:
            True if rollout successful, False if rolled back
        """
        
        print(f"\n{'='*80}")
        print(f"CANARY ROLLOUT: {self.service_name}")
        print(f"{'='*80}")
        print(f"New version: {new_version}")
        print(f"Baseline: {baseline_version}")
        print(f"Stages: {self.config.stages}%")
        print(f"{'='*80}\n")
        
        stage_results = []
        failure_count = 0
        
        for stage_percentage in self.config.stages:
            print(f"\n{'─'*80}")
            print(f"STAGE: {stage_percentage}% TRAFFIC")
            print(f"{'─'*80}")
            
            # Transition state
            state_machine.transition(
                DeploymentState.CANARY,
                f"Canary stage {stage_percentage}%",
                {'canary_percentage': stage_percentage}
            )
            
            # Update Kubernetes deployment
            if not self._apply_canary_traffic(stage_percentage, new_version):
                print(f"✗ Failed to apply {stage_percentage}% traffic")
                state_machine.transition(
                    DeploymentState.ROLLING_BACK,
                    f"Failed to apply canary traffic at {stage_percentage}%"
                )
                return False
            
            # Wait for deployment to stabilize
            print(f"⏳ Waiting {self.config.wait_time_seconds}s for metrics to stabilize...")
            state_machine.transition(
                DeploymentState.CANARY_WAITING,
                f"Waiting for metrics at {stage_percentage}%"
            )
            time.sleep(self.config.wait_time_seconds)
            
            # Wait for metrics to be available
            if not self.evaluator.wait_for_metrics(self.service_name, new_version, 30):
                print("⚠ Warning: Metrics not available, continuing...")
            
            # Evaluate health gates
            print(f"\n🔍 Evaluating health gates...")
            state_machine.transition(
                DeploymentState.CANARY_EVALUATING,
                f"Evaluating health at {stage_percentage}%"
            )
            
            start_time = time.time()
            
            gates = self.evaluator.create_standard_gates(self.service_name)
            health_result = self.evaluator.evaluate_all_gates(
                gates=gates,
                version=new_version,
                baseline_version=baseline_version
            )
            
            duration = time.time() - start_time
            
            # Record stage result
            stage_result = CanaryStageResult(
                stage_percentage=stage_percentage,
                health_gate_result=health_result,
                passed=health_result.passed,
                timestamp=datetime.now(),
                duration_seconds=duration
            )
            stage_results.append(stage_result)
            
            # Print results
            self._print_health_gate_results(health_result)
            
            # Check if health gates passed
            if not health_result.passed:
                failure_count += 1
                print(f"\n✗ Health gates FAILED at {stage_percentage}%")
                print(f"Failure count: {failure_count}/{self.config.max_failures}")
                
                if failure_count >= self.config.max_failures:
                    print(f"\n🚨 Max failures ({self.config.max_failures}) reached, triggering ROLLBACK")
                    state_machine.transition(
                        DeploymentState.ROLLING_BACK,
                        f"Health gates failed at {stage_percentage}%, max failures reached"
                    )
                    self._rollback_deployment(baseline_version)
                    return False
                else:
                    print(f"⚠ Continuing with caution...")
            else:
                print(f"\n✓ Health gates PASSED at {stage_percentage}%")
            
            # If not at 100%, continue to next stage
            if stage_percentage < 100:
                print(f"\n→ Proceeding to next stage...")
        
        # All stages passed
        print(f"\n{'='*80}")
        print(f"✓ CANARY ROLLOUT COMPLETE")
        print(f"{'='*80}")
        print(f"All stages passed, deploying to 100%")
        
        # Promote to full deployment
        state_machine.transition(
            DeploymentState.PROMOTING,
            "All canary stages passed, promoting to 100%"
        )
        
        if self._promote_to_full_deployment(new_version):
            state_machine.transition(
                DeploymentState.PROMOTED,
                "Deployment promoted to 100%"
            )
            return True
        else:
            print(f"✗ Failed to promote deployment")
            state_machine.transition(
                DeploymentState.ROLLING_BACK,
                "Failed to promote deployment"
            )
            self._rollback_deployment(baseline_version)
            return False
    
    def _apply_canary_traffic(self, percentage: int, new_version: str) -> bool:
        """Apply canary traffic percentage"""
        
        print(f"📍 Setting canary traffic to {percentage}%...")
        
        # In a real implementation, this would use kubectl or Kubernetes API
        # to update the deployment or service mesh (e.g., Istio)
        
        # Example using kubectl (requires Istio or similar):
        # kubectl apply -f virtualservice.yaml (with traffic split)
        
        # For demo purposes, we'll simulate this
        try:
            # Simulated command
            cmd = [
                "kubectl", "set", "image",
                f"deployment/{self.service_name}",
                f"{self.service_name}={new_version}",
                f"-n", self.namespace
            ]
            
            # In production, execute the command
            # result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            print(f"✓ Canary traffic set to {percentage}%")
            return True
        
        except Exception as e:
            print(f"✗ Error setting canary traffic: {e}")
            return False
    
    def _promote_to_full_deployment(self, new_version: str) -> bool:
        """Promote canary to full deployment (100%)"""
        
        print(f"\n📍 Promoting to full deployment...")
        
        try:
            # Update deployment to 100% new version
            cmd = [
                "kubectl", "set", "image",
                f"deployment/{self.service_name}",
                f"{self.service_name}={new_version}",
                f"-n", self.namespace
            ]
            
            # In production, execute the command
            # result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Wait for rollout to complete
            # kubectl rollout status deployment/{service_name} -n {namespace}
            
            print(f"✓ Deployment promoted to 100%")
            return True
        
        except Exception as e:
            print(f"✗ Error promoting deployment: {e}")
            return False
    
    def _rollback_deployment(self, baseline_version: str) -> bool:
        """Rollback deployment to baseline version"""
        
        print(f"\n🔄 Rolling back to baseline version: {baseline_version}")
        
        try:
            # Rollback using kubectl
            cmd = [
                "kubectl", "rollout", "undo",
                f"deployment/{self.service_name}",
                f"-n", self.namespace
            ]
            
            # In production, execute the command
            # result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Or set image to baseline version
            cmd_set = [
                "kubectl", "set", "image",
                f"deployment/{self.service_name}",
                f"{self.service_name}={baseline_version}",
                f"-n", self.namespace
            ]
            
            # result = subprocess.run(cmd_set, capture_output=True, text=True, check=True)
            
            print(f"✓ Rollback complete")
            return True
        
        except Exception as e:
            print(f"✗ Error during rollback: {e}")
            return False
    
    def _print_health_gate_results(self, result: HealthGateResult):
        """Print health gate evaluation results"""
        
        print(f"\nHealth Gate Results:")
        print(f"  Status: {'✓ PASS' if result.passed else '✗ FAIL'}")
        print(f"  Gates: {result.passed_gates}/{result.total_gates} passed")
        print(f"  Duration: {result.duration_seconds:.2f}s")
        print(f"\nDetailed Results:")
        
        for metric_result in result.metric_results:
            status_icon = "✓" if metric_result.status.value == "pass" else "✗"
            severity = metric_result.gate.severity.upper()
            
            print(f"  {status_icon} [{severity:8}] {metric_result.gate.name:20} | {metric_result.message}")


# Example usage
if __name__ == "__main__":
    from deployment_state_machine import DeploymentContext
    
    # Create deployment context
    context = DeploymentContext(
        deployment_id="DEP-001",
        incident_id="INC-001",
        service_name="payment-service",
        image_tag="v2.1.0-abc123",
        commit_hash="abc123def456"
    )
    
    # Initialize state machine
    state_machine = DeploymentStateMachine(context)
    
    # Initialize canary controller
    controller = CanaryController(
        service_name="payment-service",
        namespace="production",
        prometheus_url="http://localhost:9090"
    )
    
    # Execute canary rollout
    success = controller.execute_canary_rollout(
        new_version="v2.1.0-abc123",
        baseline_version="v2.0.0",
        state_machine=state_machine
    )
    
    if success:
        print("\n✓ Canary rollout successful")
    else:
        print("\n✗ Canary rollout failed, deployment rolled back")
