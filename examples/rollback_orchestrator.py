#!/usr/bin/env python3
"""
Rollback Orchestrator - Step 9 Component

Executes fast, safe rollback when verification fails.

STRATEGIES:
1. Instant Rollback - < 10 seconds, revert to previous image
2. Gradual Rollback - Step down: 100%→75%→50%→25%→0%
3. Emergency Rollback - Force delete pods, immediate recovery

Author: Step 9 - Verification Loop
Date: 2026-01-02
"""

import json
import subprocess
import time
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum


class RollbackStatus(Enum):
    """Rollback execution status"""
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"
    IN_PROGRESS = "IN_PROGRESS"


@dataclass
class RollbackResult:
    """Result of rollback execution"""
    status: RollbackStatus
    strategy_used: str
    duration_seconds: float
    
    # Details
    rolled_back_from: str      # Image tag before rollback
    rolled_back_to: str        # Image tag after rollback
    service_name: str
    namespace: str
    
    # Steps executed
    steps_completed: List[str]
    steps_failed: List[str]
    
    # Validation
    health_check_passed: bool
    pods_ready: int
    pods_total: int
    
    # Artifacts
    rollback_manifest_path: Optional[str]
    kubectl_output: str
    
    started_at: str
    completed_at: str


class RollbackOrchestrator:
    """
    Orchestrates rollback execution with multiple strategies
    
    Uses immutable deployments from Step 8 for instant rollback
    """
    
    def __init__(self, config: Dict):
        """
        Initialize orchestrator
        
        Args:
            config: Rollback configuration
        """
        self.config = config
        self.kubectl_path = config.get('kubectl_path', 'kubectl')
        self.rollback_timeout = config.get('rollback_timeout_seconds', 300)
        self.health_check_timeout = config.get('health_check_timeout_seconds', 120)
    
    def execute_rollback(self,
                        deployment_result: Dict,
                        strategy: str = 'INSTANT',
                        reason: str = "Verification failed") -> RollbackResult:
        """
        Execute rollback based on strategy
        
        Args:
            deployment_result: Original deployment result from Step 8
            strategy: 'INSTANT', 'GRADUAL', or 'EMERGENCY'
            reason: Reason for rollback
        
        Returns:
            RollbackResult
        """
        start_time = time.time()
        started_at = datetime.now().isoformat()
        
        service_name = deployment_result.get('service_name', 'unknown')
        namespace = deployment_result.get('namespace', 'production')
        current_image = deployment_result.get('image_tag', '')
        previous_image = deployment_result.get('previous_image_tag', '')
        
        print(f"\n{'='*60}")
        print(f"🔄 ROLLBACK ORCHESTRATOR")
        print(f"{'='*60}")
        print(f"Service: {service_name}")
        print(f"Namespace: {namespace}")
        print(f"Strategy: {strategy}")
        print(f"Reason: {reason}")
        print(f"Current Image: {current_image}")
        print(f"Rolling back to: {previous_image}")
        
        steps_completed = []
        steps_failed = []
        kubectl_output = []
        
        try:
            if strategy == 'INSTANT':
                result = self._instant_rollback(
                    service_name, namespace, current_image, previous_image,
                    steps_completed, steps_failed, kubectl_output
                )
            
            elif strategy == 'GRADUAL':
                result = self._gradual_rollback(
                    service_name, namespace, current_image, previous_image,
                    steps_completed, steps_failed, kubectl_output
                )
            
            elif strategy == 'EMERGENCY':
                result = self._emergency_rollback(
                    service_name, namespace, current_image, previous_image,
                    steps_completed, steps_failed, kubectl_output
                )
            
            else:
                raise ValueError(f"Unknown rollback strategy: {strategy}")
            
            # Verify rollback
            print(f"\n✅ Verifying rollback...")
            health_passed, pods_ready, pods_total = self._verify_rollback(
                service_name, namespace
            )
            
            if health_passed:
                print(f"✅ Health check passed: {pods_ready}/{pods_total} pods ready")
                status = RollbackStatus.SUCCESS
            else:
                print(f"⚠️  Health check warning: {pods_ready}/{pods_total} pods ready")
                status = RollbackStatus.PARTIAL
            
            duration = time.time() - start_time
            
            print(f"\n{'='*60}")
            print(f"Status: {status.value}")
            print(f"Duration: {duration:.1f}s")
            print(f"{'='*60}")
            
            return RollbackResult(
                status=status,
                strategy_used=strategy,
                duration_seconds=duration,
                rolled_back_from=current_image,
                rolled_back_to=previous_image,
                service_name=service_name,
                namespace=namespace,
                steps_completed=steps_completed,
                steps_failed=steps_failed,
                health_check_passed=health_passed,
                pods_ready=pods_ready,
                pods_total=pods_total,
                rollback_manifest_path=None,
                kubectl_output='\n'.join(kubectl_output),
                started_at=started_at,
                completed_at=datetime.now().isoformat()
            )
        
        except Exception as e:
            print(f"\n❌ Rollback failed: {e}")
            duration = time.time() - start_time
            
            return RollbackResult(
                status=RollbackStatus.FAILED,
                strategy_used=strategy,
                duration_seconds=duration,
                rolled_back_from=current_image,
                rolled_back_to=previous_image,
                service_name=service_name,
                namespace=namespace,
                steps_completed=steps_completed,
                steps_failed=steps_failed + [str(e)],
                health_check_passed=False,
                pods_ready=0,
                pods_total=0,
                rollback_manifest_path=None,
                kubectl_output='\n'.join(kubectl_output),
                started_at=started_at,
                completed_at=datetime.now().isoformat()
            )
    
    def _instant_rollback(self,
                         service_name: str,
                         namespace: str,
                         current_image: str,
                         previous_image: str,
                         steps_completed: List[str],
                         steps_failed: List[str],
                         kubectl_output: List[str]) -> bool:
        """
        Instant rollback using immutable deployment (Step 8 feature)
        
        Simply update image tag to previous version
        Target: < 10 seconds
        """
        print(f"\n⚡ INSTANT ROLLBACK")
        print(f"Target: < 10 seconds")
        
        # Step 1: Update image using kubectl set image
        step = f"kubectl set image deployment/{service_name} app={previous_image}"
        print(f"\n📝 Step 1: Update image")
        print(f"   Command: {step}")
        
        try:
            result = self._run_kubectl_command([
                'set', 'image',
                f'deployment/{service_name}',
                f'app={previous_image}',
                '-n', namespace
            ])
            
            kubectl_output.append(f"[set image] {result}")
            steps_completed.append("Update image to previous version")
            print(f"   ✅ Image updated")
        
        except Exception as e:
            steps_failed.append(f"Failed to update image: {e}")
            raise
        
        # Step 2: Wait for rollout (with timeout)
        print(f"\n⏳ Step 2: Wait for rollout")
        
        try:
            result = self._run_kubectl_command([
                'rollout', 'status',
                f'deployment/{service_name}',
                '-n', namespace,
                '--timeout=60s'
            ])
            
            kubectl_output.append(f"[rollout status] {result}")
            steps_completed.append("Rollout completed")
            print(f"   ✅ Rollout complete")
        
        except Exception as e:
            # Timeout is acceptable for instant rollback
            print(f"   ⚠️  Rollout in progress: {e}")
            steps_completed.append("Rollout initiated (may still be in progress)")
        
        return True
    
    def _gradual_rollback(self,
                         service_name: str,
                         namespace: str,
                         current_image: str,
                         previous_image: str,
                         steps_completed: List[str],
                         steps_failed: List[str],
                         kubectl_output: List[str]) -> bool:
        """
        Gradual rollback by stepping down traffic
        
        100% → 75% → 50% → 25% → 0% (on new version)
        Target: 2-3 minutes
        """
        print(f"\n📉 GRADUAL ROLLBACK")
        print(f"Steps: 100% → 75% → 50% → 25% → 0% (new version)")
        
        stages = [75, 50, 25, 0]
        
        for stage in stages:
            print(f"\n📊 Stage: Reduce new version to {stage}%")
            
            # In a real implementation, this would use service mesh (Istio, Linkerd)
            # or weighted services to gradually shift traffic
            
            # For now, we simulate by scaling replicas
            new_replicas = max(1, int((stage / 100) * 4))  # Assume 4 replicas total
            
            try:
                result = self._run_kubectl_command([
                    'scale',
                    f'deployment/{service_name}',
                    f'--replicas={new_replicas}',
                    '-n', namespace
                ])
                
                kubectl_output.append(f"[scale to {new_replicas}] {result}")
                steps_completed.append(f"Scaled to {stage}% ({new_replicas} replicas)")
                print(f"   ✅ Scaled to {new_replicas} replicas")
                
                # Wait between stages
                if stage > 0:
                    time.sleep(2)  # Mock: wait 2s instead of 30s
            
            except Exception as e:
                steps_failed.append(f"Failed at {stage}%: {e}")
                raise
        
        # Final step: Update to previous image
        print(f"\n📝 Final: Update to previous image")
        
        try:
            result = self._run_kubectl_command([
                'set', 'image',
                f'deployment/{service_name}',
                f'app={previous_image}',
                '-n', namespace
            ])
            
            kubectl_output.append(f"[set image] {result}")
            steps_completed.append("Updated to previous image")
            print(f"   ✅ Image updated")
        
        except Exception as e:
            steps_failed.append(f"Failed to update image: {e}")
            raise
        
        # Scale back up
        try:
            result = self._run_kubectl_command([
                'scale',
                f'deployment/{service_name}',
                '--replicas=4',
                '-n', namespace
            ])
            
            kubectl_output.append(f"[scale back] {result}")
            steps_completed.append("Scaled back to full capacity")
            print(f"   ✅ Scaled to full capacity")
        
        except Exception as e:
            steps_failed.append(f"Failed to scale back: {e}")
            raise
        
        return True
    
    def _emergency_rollback(self,
                           service_name: str,
                           namespace: str,
                           current_image: str,
                           previous_image: str,
                           steps_completed: List[str],
                           steps_failed: List[str],
                           kubectl_output: List[str]) -> bool:
        """
        Emergency rollback - forcefully restore service
        
        1. Delete all pods (force restart)
        2. Update to previous image
        3. Scale up immediately
        
        Target: < 30 seconds
        """
        print(f"\n🚨 EMERGENCY ROLLBACK")
        print(f"WARNING: Force deleting all pods")
        
        # Step 1: Update image first
        print(f"\n📝 Step 1: Update image")
        
        try:
            result = self._run_kubectl_command([
                'set', 'image',
                f'deployment/{service_name}',
                f'app={previous_image}',
                '-n', namespace
            ])
            
            kubectl_output.append(f"[set image] {result}")
            steps_completed.append("Updated image")
            print(f"   ✅ Image updated")
        
        except Exception as e:
            steps_failed.append(f"Failed to update image: {e}")
            raise
        
        # Step 2: Force delete all pods
        print(f"\n🗑️  Step 2: Force delete pods")
        
        try:
            result = self._run_kubectl_command([
                'delete', 'pods',
                '-l', f'app={service_name}',
                '-n', namespace,
                '--force',
                '--grace-period=0'
            ])
            
            kubectl_output.append(f"[delete pods] {result}")
            steps_completed.append("Force deleted all pods")
            print(f"   ✅ Pods deleted")
        
        except Exception as e:
            # Pods might already be gone
            print(f"   ⚠️  Pod deletion: {e}")
        
        # Step 3: Ensure deployment is scaled
        print(f"\n📈 Step 3: Scale deployment")
        
        try:
            result = self._run_kubectl_command([
                'scale',
                f'deployment/{service_name}',
                '--replicas=4',
                '-n', namespace
            ])
            
            kubectl_output.append(f"[scale] {result}")
            steps_completed.append("Scaled deployment")
            print(f"   ✅ Deployment scaled")
        
        except Exception as e:
            steps_failed.append(f"Failed to scale: {e}")
            raise
        
        return True
    
    def _verify_rollback(self, service_name: str, namespace: str) -> Tuple[bool, int, int]:
        """
        Verify rollback succeeded by checking pod health
        
        Returns:
            (health_passed, pods_ready, pods_total)
        """
        try:
            # Get pod status
            result = self._run_kubectl_command([
                'get', 'pods',
                '-l', f'app={service_name}',
                '-n', namespace,
                '-o', 'json'
            ])
            
            # Parse JSON to count ready pods
            import json
            pods_data = json.loads(result)
            
            pods_total = len(pods_data.get('items', []))
            pods_ready = 0
            
            for pod in pods_data.get('items', []):
                status = pod.get('status', {})
                conditions = status.get('conditions', [])
                
                for condition in conditions:
                    if condition.get('type') == 'Ready' and condition.get('status') == 'True':
                        pods_ready += 1
                        break
            
            # Health passed if at least 75% pods ready
            health_passed = pods_ready >= (pods_total * 0.75) if pods_total > 0 else False
            
            return health_passed, pods_ready, pods_total
        
        except Exception as e:
            print(f"⚠️  Failed to verify rollback: {e}")
            return False, 0, 0
    
    def _run_kubectl_command(self, args: List[str]) -> str:
        """
        Run kubectl command
        
        Args:
            args: kubectl command arguments
        
        Returns:
            Command output
        """
        # In a real implementation, this would run actual kubectl commands
        # For now, simulate success
        
        cmd = ' '.join([self.kubectl_path] + args)
        print(f"   Running: {cmd}")
        
        # Mock success
        return f"Success (mocked): {cmd}"


# Example usage
if __name__ == "__main__":
    # Configuration
    config = {
        'kubectl_path': 'kubectl',
        'rollback_timeout_seconds': 300,
        'health_check_timeout_seconds': 120
    }
    
    orchestrator = RollbackOrchestrator(config)
    
    # Mock deployment result from Step 8
    deployment_result = {
        'service_name': 'payment-service',
        'namespace': 'production',
        'image_tag': 'payment-service:abc123-1641024000',
        'previous_image_tag': 'payment-service:xyz789-1641020000',
        'deployment_id': 'DEP-abc123'
    }
    
    # Scenario 1: Instant rollback
    print("="*60)
    print("SCENARIO 1: INSTANT ROLLBACK")
    print("="*60)
    
    result1 = orchestrator.execute_rollback(
        deployment_result,
        strategy='INSTANT',
        reason='Critical error rate increase'
    )
    
    # Scenario 2: Gradual rollback
    print("\n" + "="*60)
    print("SCENARIO 2: GRADUAL ROLLBACK")
    print("="*60)
    
    result2 = orchestrator.execute_rollback(
        deployment_result,
        strategy='GRADUAL',
        reason='Moderate latency degradation'
    )
    
    # Scenario 3: Emergency rollback
    print("\n" + "="*60)
    print("SCENARIO 3: EMERGENCY ROLLBACK")
    print("="*60)
    
    result3 = orchestrator.execute_rollback(
        deployment_result,
        strategy='EMERGENCY',
        reason='Service completely down'
    )
    
    # Save results
    results = {
        'instant_rollback': asdict(result1),
        'gradual_rollback': asdict(result2),
        'emergency_rollback': asdict(result3)
    }
    
    # Convert enums
    for scenario in results.values():
        scenario['status'] = scenario['status'] if isinstance(scenario['status'], str) else scenario['status'].value
    
    with open('rollback_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Rollback results saved to: rollback_results.json")
