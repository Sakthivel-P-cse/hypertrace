#!/usr/bin/env python3
"""
Concurrency Orchestrator

Central coordinator integrating all Step 10 components:
- Distributed locking (deadlock prevention via lock ordering)
- Dependency-aware conflict detection (uses RCA graph)
- Safety gate checks (pre-action validation)
- State machine coordination (with human override)
- Audit logging (tamper-evident hash chain)
- Multi-channel notifications

Integration with Steps 8 & 9:
- Wraps deployment operations from Step 8
- Wraps verification operations from Step 9
- Ensures safe concurrent operations

Key Design Principles:
1. Safety First: Check all gates before action
2. Dependency Awareness: Use RCA graph to detect hidden conflicts
3. Deadlock Prevention: Enforce lock ordering rules
4. Human Override: Pause for review when needed
5. Complete Audit Trail: Every action logged with hash chain
6. Clear Notifications: Keep stakeholders informed

Example Usage:
    orchestrator = ConcurrencyOrchestrator(config)
    
    # Safe deployment with all checks
    result = await orchestrator.execute_operation(
        operation_type=OperationType.DEPLOYMENT,
        service_name='payment-service',
        operation_data={
            'version': '1.2.3',
            'strategy': 'canary'
        }
    )
"""

import asyncio
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass
import logging

# Import all Step 10 components
from distributed_lock_manager import DistributedLockManager, LockScope
from audit_logger import AuditLogger, ActionCategory, ActionSeverity
from conflict_detector import DependencyAwareConflictDetector, OperationType, ConflictType
from safety_gate_checker import SafetyGateChecker
from concurrency_state_machine import ConcurrencyStateMachine, ConcurrencyState
from notifier import Notifier, NotificationSeverity, NotificationChannel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OperationResult(Enum):
    """Result of orchestrated operation"""
    SUCCESS = "success"
    FAILED = "failed"
    PAUSED_FOR_REVIEW = "paused_for_review"
    BLOCKED_BY_CONFLICT = "blocked_by_conflict"
    BLOCKED_BY_SAFETY_GATE = "blocked_by_safety_gate"
    DEADLOCK_DETECTED = "deadlock_detected"
    TIMEOUT = "timeout"


@dataclass
class ExecutionResult:
    """Result of operation execution"""
    result: OperationResult
    operation_id: str
    service_name: str
    operation_type: OperationType
    duration_seconds: float
    
    # Details
    lock_acquired: bool
    safety_gates_passed: bool
    conflicts_detected: List[str]
    state_transitions: List[str]
    
    # Audit trail
    correlation_id: str
    audit_events: List[str]
    
    # Human intervention
    paused: bool
    pause_reason: Optional[str] = None
    
    # Error info
    error: Optional[str] = None
    rollback_performed: bool = False


class ConcurrencyOrchestrator:
    """
    Central coordinator for safe concurrent operations.
    
    Integrates all Step 10 components to provide:
    1. Distributed locking with deadlock prevention
    2. Dependency-aware conflict detection using RCA graph
    3. Safety gate validation before operations
    4. State machine coordination with human override
    5. Comprehensive audit logging with hash chain
    6. Multi-channel notifications
    
    Workflow:
    1. Initialize state machine (INIT)
    2. Register operation with conflict detector
    3. Detect conflicts using dependency graph
    4. Acquire distributed lock (enforcing lock ordering)
    5. Check safety gates (error budget, blast radius, etc.)
    6. Execute operation (DEPLOYMENT, VERIFICATION, etc.)
    7. Handle human override if needed (PAUSED_FOR_HUMAN_REVIEW)
    8. Release lock and cleanup
    9. Audit all actions with hash chain
    10. Notify stakeholders
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize orchestrator with all components.
        
        Args:
            config: Configuration dict with:
                - redis_host, redis_port: For distributed locking
                - neo4j_uri, neo4j_user, neo4j_password: For dependency graph
                - elasticsearch_url: For audit logging
                - slack_webhook, pagerduty_key: For notifications
                - error_budget_pct, max_blast_radius_pct: Safety thresholds
                - lock_timeout_seconds, operation_timeout_seconds: Timeouts
        """
        self.config = config
        
        # Initialize all Step 10 components
        self.lock_manager = DistributedLockManager(
            redis_host=config.get('redis_host', 'localhost'),
            redis_port=config.get('redis_port', 6379),
            use_redis=config.get('use_redis', False)  # Use file-based for dev
        )
        
        self.audit_logger = AuditLogger(
            log_file=config.get('audit_log_file', '/var/log/concurrency_audit.jsonl'),
            elasticsearch_url=config.get('elasticsearch_url')
        )
        
        self.conflict_detector = DependencyAwareConflictDetector(
            neo4j_uri=config.get('neo4j_uri'),
            neo4j_user=config.get('neo4j_user', 'neo4j'),
            neo4j_password=config.get('neo4j_password')
        )
        
        self.safety_gate_checker = SafetyGateChecker(config)
        
        self.notifier = Notifier({
            'enabled_channels': config.get('notification_channels', ['slack']),
            'slack_webhook': config.get('slack_webhook'),
            'pagerduty_key': config.get('pagerduty_key')
        })
        
        # Operation timeout
        self.operation_timeout = config.get('operation_timeout_seconds', 600)
        
        logger.info("✅ ConcurrencyOrchestrator initialized with all Step 10 components")
    
    async def execute_operation(
        self,
        operation_type: OperationType,
        service_name: str,
        operation_data: Dict[str, Any],
        correlation_id: Optional[str] = None,
        actor: str = "system"
    ) -> ExecutionResult:
        """
        Execute operation with full concurrency control.
        
        This is the main entry point for all operations (deployment, verification, rollback, etc.)
        
        Workflow:
        1. Generate operation ID and correlation ID
        2. Initialize state machine
        3. Register operation with conflict detector
        4. Check for conflicts using dependency graph
        5. Acquire distributed lock (with deadlock prevention)
        6. Validate safety gates
        7. Execute actual operation
        8. Handle human override if needed
        9. Release lock and cleanup
        10. Audit all actions
        11. Send notifications
        
        Args:
            operation_type: Type of operation (DEPLOYMENT, VERIFICATION, etc.)
            service_name: Target service name
            operation_data: Operation-specific data (version, config, etc.)
            correlation_id: Optional correlation ID (generated if not provided)
            actor: Who initiated the operation (user, system, etc.)
        
        Returns:
            ExecutionResult with detailed execution information
        """
        import time
        import uuid
        
        # Generate IDs
        operation_id = str(uuid.uuid4())[:8]
        correlation_id = correlation_id or str(uuid.uuid4())
        start_time = time.time()
        
        logger.info(f"\n{'='*80}")
        logger.info(f"🚀 STARTING OPERATION: {operation_type.value}")
        logger.info(f"   Service: {service_name}")
        logger.info(f"   Operation ID: {operation_id}")
        logger.info(f"   Correlation ID: {correlation_id}")
        logger.info(f"   Actor: {actor}")
        logger.info(f"{'='*80}\n")
        
        # Initialize result
        result = ExecutionResult(
            result=OperationResult.SUCCESS,
            operation_id=operation_id,
            service_name=service_name,
            operation_type=operation_type,
            duration_seconds=0.0,
            lock_acquired=False,
            safety_gates_passed=False,
            conflicts_detected=[],
            state_transitions=[],
            correlation_id=correlation_id,
            audit_events=[],
            paused=False
        )
        
        # Initialize state machine
        state_machine = ConcurrencyStateMachine(
            operation_id=operation_id,
            operation_type=operation_type.value,
            service_name=service_name
        )
        result.state_transitions.append(f"INIT")
        
        try:
            # Step 1: Register operation with conflict detector
            logger.info("📝 Step 1: Registering operation with conflict detector...")
            self.conflict_detector.register_operation(
                operation_id=operation_id,
                operation_type=operation_type,
                service_name=service_name,
                estimated_duration_minutes=operation_data.get('estimated_duration_minutes', 10),
                metadata=operation_data
            )
            self.audit_logger.log_event(
                category=ActionCategory.CONFLICT_DETECTION,
                action="operation_registered",
                severity=ActionSeverity.INFO,
                service_name=service_name,
                actor=actor,
                details={
                    'operation_id': operation_id,
                    'operation_type': operation_type.value
                },
                correlation_id=correlation_id
            )
            result.audit_events.append("operation_registered")
            
            # Step 2: Detect conflicts using dependency graph
            logger.info("🔍 Step 2: Detecting conflicts using dependency-aware detection...")
            conflict_result = self.conflict_detector.detect_conflicts(
                operation_id=operation_id
            )
            
            if conflict_result.has_conflict:
                logger.warning(f"⚠️  CONFLICT DETECTED: {conflict_result.conflict_type.value}")
                logger.warning(f"   Severity: {conflict_result.severity}")
                logger.warning(f"   Blast Radius: {conflict_result.blast_radius} services")
                logger.warning(f"   Affected Services: {', '.join(conflict_result.affected_services)}")
                logger.warning(f"   Explanation: {conflict_result.explanation}")
                logger.warning(f"   Recommendation: {conflict_result.recommendation}")
                
                result.conflicts_detected = [
                    f"{conflict_result.conflict_type.value}: {conflict_result.explanation}"
                ]
                
                # Log conflict to audit trail
                self.audit_logger.log_conflict_detected(
                    service_name=service_name,
                    conflict_type=conflict_result.conflict_type.value,
                    severity=conflict_result.severity,
                    conflicting_operations=conflict_result.conflicting_operations,
                    blast_radius=conflict_result.blast_radius,
                    actor=actor,
                    correlation_id=correlation_id
                )
                result.audit_events.append("conflict_detected")
                
                # Notify stakeholders about conflict
                self.notifier.send(
                    title=f"Conflict Detected: {service_name}",
                    message=f"{conflict_result.conflict_type.value}: {conflict_result.explanation}\n"
                            f"Blast Radius: {conflict_result.blast_radius} services\n"
                            f"Recommendation: {conflict_result.recommendation}",
                    severity=NotificationSeverity.WARNING,
                    metadata={
                        'operation_id': operation_id,
                        'service_name': service_name,
                        'conflict_type': conflict_result.conflict_type.value
                    }
                )
                
                # Check if conflict is critical
                if conflict_result.conflict_type in [ConflictType.DIRECT, ConflictType.SHARED_RESOURCE]:
                    logger.error("🛑 CRITICAL CONFLICT - Operation blocked")
                    result.result = OperationResult.BLOCKED_BY_CONFLICT
                    
                    # Transition to FAILED state
                    state_machine.transition(
                        new_state=ConcurrencyState.FAILED,
                        actor=actor,
                        metadata={'reason': 'blocked_by_conflict'}
                    )
                    result.state_transitions.append("FAILED (conflict)")
                    
                    return result
                else:
                    # Non-critical conflict: Pause for human review
                    logger.warning("⏸️  NON-CRITICAL CONFLICT - Pausing for human review...")
                    state_machine.pause_for_review(
                        reason=f"Conflict detected: {conflict_result.explanation}",
                        paused_by=actor,
                        severity="medium"
                    )
                    result.state_transitions.append("PAUSED_FOR_HUMAN_REVIEW (conflict)")
                    result.paused = True
                    result.pause_reason = conflict_result.explanation
                    result.result = OperationResult.PAUSED_FOR_REVIEW
                    
                    # Log human intervention needed
                    self.audit_logger.log_manual_intervention(
                        service_name=service_name,
                        reason=f"Conflict detected: {conflict_result.explanation}",
                        requested_by=actor,
                        severity="medium",
                        correlation_id=correlation_id
                    )
                    result.audit_events.append("manual_intervention_requested")
                    
                    # Notify stakeholders that human review is needed
                    self.notifier.send(
                        title=f"Human Review Required: {service_name}",
                        message=f"Operation paused due to conflict:\n{conflict_result.explanation}\n\n"
                                f"Please review and approve/reject.",
                        severity=NotificationSeverity.WARNING,
                        channels=[NotificationChannel.SLACK, NotificationChannel.EMAIL]
                    )
                    
                    return result
            else:
                logger.info("✅ No conflicts detected - proceeding")
            
            # Step 3: Acquire distributed lock (with deadlock prevention)
            logger.info("🔒 Step 3: Acquiring distributed lock...")
            
            # Determine lock scope based on operation type
            lock_scope = self._get_lock_scope(operation_type)
            
            # Transition to LOCKED state
            state_machine.transition(
                new_state=ConcurrencyState.LOCKED,
                actor=actor,
                metadata={'lock_scope': lock_scope.value}
            )
            result.state_transitions.append("LOCKED")
            
            # Try to acquire lock
            lock_acquired = self.lock_manager.acquire_lock(
                resource_id=service_name,
                holder_id=operation_id,
                scope=lock_scope,
                ttl_seconds=self.config.get('lock_ttl_seconds', 300),
                wait_timeout_seconds=self.config.get('lock_wait_timeout_seconds', 30)
            )
            
            if not lock_acquired:
                logger.error(f"🛑 Failed to acquire lock for {service_name}")
                
                # Log lock failure
                self.audit_logger.log_lock_failed(
                    resource_id=service_name,
                    holder_id=operation_id,
                    lock_scope=lock_scope.value,
                    reason="timeout",
                    actor=actor,
                    correlation_id=correlation_id
                )
                result.audit_events.append("lock_failed")
                
                # Notify about lock failure
                self.notifier.send(
                    title=f"Lock Acquisition Failed: {service_name}",
                    message=f"Could not acquire lock for {operation_type.value}",
                    severity=NotificationSeverity.ERROR
                )
                
                result.result = OperationResult.TIMEOUT
                state_machine.transition(ConcurrencyState.FAILED, actor, {'reason': 'lock_timeout'})
                result.state_transitions.append("FAILED (lock timeout)")
                return result
            
            result.lock_acquired = True
            logger.info(f"✅ Lock acquired: {service_name} (scope={lock_scope.value})")
            
            # Log successful lock acquisition
            self.audit_logger.log_lock_acquired(
                resource_id=service_name,
                holder_id=operation_id,
                lock_scope=lock_scope.value,
                ttl_seconds=self.config.get('lock_ttl_seconds', 300),
                actor=actor,
                correlation_id=correlation_id
            )
            result.audit_events.append("lock_acquired")
            
            # Step 4: Check safety gates
            logger.info("🚦 Step 4: Checking safety gates...")
            
            # Transition to SAFETY_CHECK state
            state_machine.transition(
                new_state=ConcurrencyState.SAFETY_CHECK,
                actor=actor
            )
            result.state_transitions.append("SAFETY_CHECK")
            
            # Check all safety gates
            gates_passed, gate_results = self.safety_gate_checker.check_all_gates(
                service_name=service_name,
                operation_type=operation_type.value,
                estimated_blast_radius=conflict_result.blast_radius if conflict_result else 1
            )
            
            if not gates_passed:
                logger.warning("⚠️  Safety gates failed:")
                for gate_result in gate_results:
                    if not gate_result.passed:
                        logger.warning(f"   ❌ {gate_result.gate_type.value}: {gate_result.reason}")
                
                # Log safety gate failure
                self.audit_logger.log_safety_gate_result(
                    service_name=service_name,
                    gates_checked=[gr.gate_type.value for gr in gate_results],
                    gates_passed=gates_passed,
                    failed_gates=[gr.gate_type.value for gr in gate_results if not gr.passed],
                    actor=actor,
                    correlation_id=correlation_id
                )
                result.audit_events.append("safety_gates_failed")
                
                # Pause for human review
                logger.warning("⏸️  Pausing for human review due to safety gate failures...")
                state_machine.pause_for_review(
                    reason=f"Safety gates failed: {[gr.gate_type.value for gr in gate_results if not gr.passed]}",
                    paused_by=actor,
                    severity="high"
                )
                result.state_transitions.append("PAUSED_FOR_HUMAN_REVIEW (safety gates)")
                result.paused = True
                result.pause_reason = "Safety gates failed"
                result.result = OperationResult.BLOCKED_BY_SAFETY_GATE
                
                # Notify about safety gate failure
                self.notifier.send(
                    title=f"Safety Gates Failed: {service_name}",
                    message=f"Operation paused - safety gates failed:\n" +
                            "\n".join([f"- {gr.gate_type.value}: {gr.reason}" 
                                     for gr in gate_results if not gr.passed]),
                    severity=NotificationSeverity.ERROR,
                    channels=[NotificationChannel.SLACK, NotificationChannel.PAGERDUTY]
                )
                
                return result
            
            result.safety_gates_passed = True
            logger.info("✅ All safety gates passed")
            
            # Log safety gate success
            self.audit_logger.log_safety_gate_result(
                service_name=service_name,
                gates_checked=[gr.gate_type.value for gr in gate_results],
                gates_passed=True,
                failed_gates=[],
                actor=actor,
                correlation_id=correlation_id
            )
            result.audit_events.append("safety_gates_passed")
            
            # Step 5: Execute operation
            logger.info(f"⚙️  Step 5: Executing {operation_type.value}...")
            
            # Transition to IN_PROGRESS state
            state_machine.transition(
                new_state=ConcurrencyState.IN_PROGRESS,
                actor=actor
            )
            result.state_transitions.append("IN_PROGRESS")
            
            # Execute actual operation (delegated to Step 8/9 components)
            operation_success = await self._execute_actual_operation(
                operation_type=operation_type,
                service_name=service_name,
                operation_data=operation_data,
                correlation_id=correlation_id
            )
            
            if operation_success:
                logger.info(f"✅ {operation_type.value} completed successfully")
                
                # Transition to COMPLETED state
                state_machine.transition(
                    new_state=ConcurrencyState.COMPLETED,
                    actor=actor
                )
                result.state_transitions.append("COMPLETED")
                result.result = OperationResult.SUCCESS
                
                # Log successful operation
                if operation_type == OperationType.DEPLOYMENT:
                    self.audit_logger.log_deployment(
                        service_name=service_name,
                        version=operation_data.get('version', 'unknown'),
                        strategy=operation_data.get('strategy', 'unknown'),
                        success=True,
                        actor=actor,
                        correlation_id=correlation_id
                    )
                elif operation_type == OperationType.VERIFICATION:
                    self.audit_logger.log_verification(
                        service_name=service_name,
                        verification_type=operation_data.get('verification_type', 'health_check'),
                        result='passed',
                        actor=actor,
                        correlation_id=correlation_id
                    )
                elif operation_type == OperationType.ROLLBACK:
                    self.audit_logger.log_rollback(
                        service_name=service_name,
                        from_version=operation_data.get('from_version', 'unknown'),
                        to_version=operation_data.get('to_version', 'unknown'),
                        reason='manual_rollback',
                        success=True,
                        actor=actor,
                        correlation_id=correlation_id
                    )
                result.audit_events.append(f"{operation_type.value}_success")
                
                # Notify success
                self.notifier.send(
                    title=f"{operation_type.value.title()} Successful: {service_name}",
                    message=f"{operation_type.value} completed successfully",
                    severity=NotificationSeverity.INFO
                )
                
            else:
                logger.error(f"❌ {operation_type.value} failed")
                
                # Transition to FAILED state
                state_machine.transition(
                    new_state=ConcurrencyState.FAILED,
                    actor=actor,
                    metadata={'reason': 'operation_failed'}
                )
                result.state_transitions.append("FAILED (operation)")
                result.result = OperationResult.FAILED
                
                # Log failed operation
                if operation_type == OperationType.DEPLOYMENT:
                    self.audit_logger.log_deployment(
                        service_name=service_name,
                        version=operation_data.get('version', 'unknown'),
                        strategy=operation_data.get('strategy', 'unknown'),
                        success=False,
                        actor=actor,
                        correlation_id=correlation_id
                    )
                result.audit_events.append(f"{operation_type.value}_failed")
                
                # Notify failure
                self.notifier.send(
                    title=f"{operation_type.value.title()} Failed: {service_name}",
                    message=f"{operation_type.value} failed - manual intervention may be needed",
                    severity=NotificationSeverity.ERROR,
                    channels=[NotificationChannel.SLACK, NotificationChannel.EMAIL]
                )
        
        except Exception as e:
            logger.error(f"❌ Exception during operation: {e}")
            result.result = OperationResult.FAILED
            result.error = str(e)
            
            # Transition to FAILED state
            try:
                state_machine.transition(
                    new_state=ConcurrencyState.FAILED,
                    actor=actor,
                    metadata={'error': str(e)}
                )
                result.state_transitions.append("FAILED (exception)")
            except:
                pass
            
            # Notify exception
            self.notifier.send(
                title=f"Operation Exception: {service_name}",
                message=f"Exception during {operation_type.value}: {str(e)}",
                severity=NotificationSeverity.CRITICAL,
                channels=[NotificationChannel.SLACK, NotificationChannel.PAGERDUTY]
            )
        
        finally:
            # Step 6: Release lock and cleanup
            if result.lock_acquired:
                logger.info("🔓 Releasing lock...")
                released = self.lock_manager.release_lock(
                    resource_id=service_name,
                    holder_id=operation_id,
                    scope=lock_scope
                )
                
                if released:
                    logger.info("✅ Lock released successfully")
                    self.audit_logger.log_lock_released(
                        resource_id=service_name,
                        holder_id=operation_id,
                        lock_scope=lock_scope.value,
                        actor=actor,
                        correlation_id=correlation_id
                    )
                    result.audit_events.append("lock_released")
                else:
                    logger.warning("⚠️  Failed to release lock (may have expired)")
            
            # Unregister operation
            self.conflict_detector.unregister_operation(operation_id)
            
            # Calculate duration
            result.duration_seconds = time.time() - start_time
            
            logger.info(f"\n{'='*80}")
            logger.info(f"🏁 OPERATION COMPLETE: {operation_type.value}")
            logger.info(f"   Result: {result.result.value}")
            logger.info(f"   Duration: {result.duration_seconds:.2f}s")
            logger.info(f"   State Transitions: {' → '.join(result.state_transitions)}")
            logger.info(f"   Audit Events: {len(result.audit_events)}")
            logger.info(f"{'='*80}\n")
        
        return result
    
    def _get_lock_scope(self, operation_type: OperationType) -> LockScope:
        """Determine lock scope based on operation type"""
        if operation_type in [OperationType.DEPLOYMENT, OperationType.ROLLBACK]:
            return LockScope.SERVICE
        elif operation_type == OperationType.VERIFICATION:
            return LockScope.INCIDENT
        else:
            return LockScope.SERVICE
    
    async def _execute_actual_operation(
        self,
        operation_type: OperationType,
        service_name: str,
        operation_data: Dict[str, Any],
        correlation_id: str
    ) -> bool:
        """
        Execute the actual operation.
        
        In production, this would delegate to:
        - Step 8 (Deployment Engine) for DEPLOYMENT operations
        - Step 9 (Verification Engine) for VERIFICATION operations
        - Rollback handler for ROLLBACK operations
        
        For now, simulate with delay.
        """
        logger.info(f"   Executing {operation_type.value} for {service_name}...")
        
        # Simulate operation with delay
        await asyncio.sleep(2)
        
        # Simulate 90% success rate
        import random
        return random.random() < 0.9
    
    def get_orchestrator_status(self) -> Dict[str, Any]:
        """Get current orchestrator status"""
        return {
            'active_locks': len(self.lock_manager.get_active_locks()),
            'ongoing_operations': len(self.conflict_detector._ongoing_operations),
            'audit_event_count': len(self.audit_logger._event_buffer),
            'config': {
                'redis_enabled': self.lock_manager.use_redis,
                'neo4j_enabled': self.conflict_detector.neo4j_enabled,
                'elasticsearch_enabled': self.audit_logger.elasticsearch_url is not None
            }
        }


# Example usage
if __name__ == '__main__':
    import asyncio
    from pathlib import Path
    from config_loader import load_config
    
    # Load configuration from YAML file (with env var expansion)
    try:
        config_path = Path(__file__).parent / 'concurrency_config.yaml'
        yaml_config = load_config(str(config_path))
        
        # Extract relevant settings
        config = {
            # Locking
            'use_redis': yaml_config['locking']['backend'] == 'redis',
            'lock_ttl_seconds': yaml_config['locking']['default_ttl_seconds'],
            'lock_wait_timeout_seconds': yaml_config['locking']['wait_timeout_seconds'],
            
            # Safety gates  
            'error_budget_pct': yaml_config['safety_gates']['error_budget']['threshold_pct'],
            'max_blast_radius_pct': yaml_config['safety_gates']['blast_radius']['max_services_pct'],
            'cooldown_seconds': yaml_config['safety_gates']['cooldown']['min_seconds_since_last_deploy'],
            
            # Notifications
            'notification_channels': list(yaml_config['notifications']['routing']['INFO']['channels'])
        }
        logger.info("Loaded configuration from concurrency_config.yaml")
    except Exception as e:
        logger.warning(f"Could not load config: {e}. Using defaults.")
        # Configuration
        config = {
            # Locking
            'use_redis': False,  # Use file-based locks for demo
            'lock_ttl_seconds': 300,
            'lock_wait_timeout_seconds': 30,
            
            # Safety gates
            'error_budget_pct': 2.0,
            'max_blast_radius_pct': 20.0,
            'cooldown_seconds': 300,
            
            # Notifications
            'notification_channels': ['slack', 'email']
        }
    
    # Create orchestrator
    orchestrator = ConcurrencyOrchestrator(config)
    
    async def demo():
        """Demonstrate orchestrated operation"""
        
        # Example 1: Successful deployment
        print("\n" + "="*80)
        print("DEMO: Successful Deployment")
        print("="*80)
        result1 = await orchestrator.execute_operation(
            operation_type=OperationType.DEPLOYMENT,
            service_name='payment-service',
            operation_data={
                'version': '1.2.3',
                'strategy': 'canary',
                'estimated_duration_minutes': 10
            },
            actor='alice@example.com'
        )
        print(f"\n✅ Result: {result1.result.value}")
        print(f"   Duration: {result1.duration_seconds:.2f}s")
        print(f"   State Transitions: {' → '.join(result1.state_transitions)}")
        
        # Example 2: Operation with conflict
        print("\n" + "="*80)
        print("DEMO: Operation with Conflict")
        print("="*80)
        
        # Start first operation
        task1 = asyncio.create_task(orchestrator.execute_operation(
            operation_type=OperationType.DEPLOYMENT,
            service_name='user-service',
            operation_data={
                'version': '2.0.0',
                'strategy': 'blue_green',
                'estimated_duration_minutes': 15
            },
            actor='bob@example.com'
        ))
        
        # Wait a bit, then try conflicting operation
        await asyncio.sleep(1)
        
        result2 = await orchestrator.execute_operation(
            operation_type=OperationType.DEPLOYMENT,
            service_name='user-service',  # Same service!
            operation_data={
                'version': '2.0.1',
                'strategy': 'canary'
            },
            actor='charlie@example.com'
        )
        
        print(f"\n⚠️  Result: {result2.result.value}")
        if result2.conflicts_detected:
            print(f"   Conflicts: {result2.conflicts_detected}")
        
        # Wait for first operation to complete
        await task1
        
        # Show orchestrator status
        print("\n" + "="*80)
        print("Orchestrator Status")
        print("="*80)
        status = orchestrator.get_orchestrator_status()
        print(f"Active Locks: {status['active_locks']}")
        print(f"Ongoing Operations: {status['ongoing_operations']}")
        print(f"Audit Events: {status['audit_event_count']}")
        print(f"Redis Enabled: {status['config']['redis_enabled']}")
        print(f"Neo4j Enabled: {status['config']['neo4j_enabled']}")
        print(f"Elasticsearch Enabled: {status['config']['elasticsearch_enabled']}")
    
    # Run demo
    asyncio.run(demo())
