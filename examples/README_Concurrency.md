# Step 10: Concurrency & Safety Controls

## Table of Contents
- [Overview](#overview)
- [Architecture](#architecture)
- [Components](#components)
- [Advanced Features](#advanced-features)
- [Workflows](#workflows)
- [Configuration](#configuration)
- [Integration](#integration)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)

## Overview

Step 10 implements **enterprise-grade concurrency control** for the self-healing system, ensuring that multiple operations can execute safely without race conditions, conflicts, or system instability.

### Problem Statement

In a distributed self-healing system, multiple operations may attempt to modify the same services simultaneously:
- **Auto-healing**: System detects incident and attempts auto-fix
- **Manual deployment**: Engineer deploys new version
- **Verification**: Health checks running concurrently
- **Rollback**: Triggered by failed verification

Without coordination, these operations can:
- **Corrupt state**: Race conditions lead to inconsistent deployments
- **Cascade failures**: Unaware deployments trigger cascading incidents
- **Deadlock**: Circular dependencies cause system freeze
- **Exhaust error budget**: Too many risky operations drain safety margins

### Solution

Step 10 provides **5-layer defense**:

1. **Distributed Locking**: Prevent race conditions via Redis/etcd locks
2. **Conflict Detection**: Dependency-aware detection using RCA graph
3. **Safety Gates**: Pre-action validation (error budget, blast radius, cooldown)
4. **Human Override**: PAUSED_FOR_HUMAN_REVIEW state for responsible automation
5. **Audit Logging**: Tamper-evident hash chain for compliance

### Key Principles

- **Safety First**: Block unsafe operations before execution
- **Dependency Awareness**: Use RCA graph to detect hidden conflicts
- **Deadlock Prevention**: Enforce lock ordering rules
- **Human-in-the-Loop**: Pause for review when needed
- **Complete Auditability**: Every action logged with hash chain

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   CONCURRENCY ORCHESTRATOR                       │
│  (Central coordinator integrating all Step 10 components)        │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
    ┌─────────────┐  ┌──────────────┐  ┌────────────┐
    │  LOCK MGR   │  │   CONFLICT   │  │  SAFETY    │
    │             │  │   DETECTOR   │  │  GATES     │
    │ Redis/File  │  │  Neo4j Graph │  │  Checker   │
    └─────────────┘  └──────────────┘  └────────────┘
              │               │               │
              └───────────────┼───────────────┘
                              ▼
                    ┌──────────────────┐
                    │  STATE MACHINE   │
                    │ (Human Override) │
                    └──────────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
    ┌─────────────┐  ┌──────────────┐  ┌────────────┐
    │   AUDIT     │  │    NOTIFIER  │  │ DEPLOYMENT │
    │   LOGGER    │  │              │  │  ENGINE    │
    │ Hash Chain  │  │ Multi-channel│  │ (Step 8/9) │
    └─────────────┘  └──────────────┘  └────────────┘
```

### Component Interactions

```
Operation Request
     │
     ▼
[1] Orchestrator registers operation
     │
     ▼
[2] Conflict Detector checks dependency graph
     │
     ├──► Conflict? ──Yes──► Pause for review
     │                        │
     ▼                        ▼
     No                   PAUSED_FOR_HUMAN_REVIEW
     │                        │
     ▼                        │ (Human approves)
[3] Acquire distributed lock  │
     │                        │
     ├──► Lock failed? ───────┤
     │                        │
     ▼                        │
     Success                  │
     │                        │
     ▼                        ▼
[4] Check safety gates    Resume
     │
     ├──► Gate failed? ──Yes──► Pause for review
     │
     ▼
     All passed
     │
     ▼
[5] Execute operation (Step 8/9)
     │
     ▼
[6] Release lock
     │
     ▼
[7] Audit log + Notify stakeholders
     │
     ▼
   Complete
```

## Components

### 1. Distributed Lock Manager

**Purpose**: Prevent race conditions by ensuring exclusive access to resources.

**Implementation**: [distributed_lock_manager.py](distributed_lock_manager.py) (~700 lines)

**Key Features**:
- **Multi-backend support**: Redis (production), etcd, Kubernetes Lease, file-based (dev)
- **Lock ordering rules**: SYSTEM(1) > SERVICE(2) > INCIDENT(3) > DEPLOYMENT(4)
- **Deadlock prevention**: Enforces lock hierarchy + alphabetical ordering
- **Auto-expiry**: Locks expire after TTL to prevent stuck locks
- **Health monitoring**: Tracks active locks, detects stale locks

**Lock Ordering Rules** (CRITICAL for deadlock prevention):

```python
class LockScope(Enum):
    SYSTEM = 1      # System-wide operations (maintenance, upgrades)
    SERVICE = 2     # Service-level operations (deployments, rollbacks)
    INCIDENT = 3    # Incident-specific operations (verification, fixes)
    DEPLOYMENT = 4  # Deployment-specific operations (canary, blue-green)
```

**Example: Preventing Deadlock**

```python
# ❌ WRONG: This causes deadlock!
# Thread A: Lock payment-service (SERVICE), then postgres (SYSTEM)
# Thread B: Lock postgres (SYSTEM), then payment-service (SERVICE)

# ✅ CORRECT: Always lock in order (SYSTEM → SERVICE)
lock_manager.acquire_lock('postgres', 'op-1', scope=LockScope.SYSTEM)
lock_manager.acquire_lock('payment-service', 'op-1', scope=LockScope.SERVICE)
```

**Documented Deadlock Scenarios**:

1. **Circular Dependencies**:
   - Service A depends on Service B
   - Service B depends on Service A
   - Both try to deploy simultaneously
   - **Prevention**: Use dependency graph to detect cycles

2. **Inconsistent Ordering**:
   - Operation 1: Lock DB → Lock Service
   - Operation 2: Lock Service → Lock DB
   - **Prevention**: Enforce lock ordering rules

3. **Long-Running Operations**:
   - Operation holds lock indefinitely
   - Other operations wait forever
   - **Prevention**: Lock TTL with auto-expiry

**Redis Implementation** (production):

```python
# Atomic lock acquisition using Lua script
acquire_script = """
if redis.call('exists', KEYS[1]) == 0 then
    redis.call('set', KEYS[1], ARGV[1], 'EX', ARGV[2])
    return 1
else
    return 0
end
"""
```

**File-Based Implementation** (development):

```python
# Uses fcntl.flock() for exclusive locks
import fcntl
lock_file = open(f'/tmp/locks/{resource_id}.lock', 'w')
fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
```

### 2. Audit Logger

**Purpose**: Comprehensive audit trail for compliance, forensics, and debugging.

**Implementation**: [audit_logger.py](audit_logger.py) (~650 lines)

**Key Features**:
- **Hash chain**: Tamper-evident logging using SHA-256
- **Multi-backend**: File (JSON lines), Elasticsearch (optional)
- **15 action categories**: Covers all Steps 1-10
- **Correlation ID tracking**: Links related operations
- **Convenience methods**: Pre-built methods for common events

**Hash Chain Mechanism**:

```python
# Each event includes hash of previous event
event_hash = sha256(previous_hash + event_json).hexdigest()

# Tampering detection
for i in range(1, len(events)):
    expected_hash = compute_hash(events[i-1], events[i])
    if events[i].event_hash != expected_hash:
        raise TamperDetected(f"Event {i} tampered!")
```

**Action Categories**:

```python
class ActionCategory(Enum):
    INCIDENT_DETECTION      # Step 1: Incident detected
    ROOT_CAUSE_ANALYSIS     # Step 3: RCA performed
    CODE_LOCALIZATION       # Step 4: Code location found
    FIX_PLANNING            # Step 5: Fix plan generated
    PATCH_GENERATION        # Step 6: Patch created
    SAFETY_GATES            # Step 7: Safety gate checked
    DEPLOYMENT              # Step 8: Deployment executed
    VERIFICATION            # Step 9: Verification performed
    ROLLBACK                # Step 9: Rollback executed
    LOCK_OPERATION          # Step 10: Lock acquired/released
    CONFLICT_DETECTION      # Step 10: Conflict detected
    STATE_TRANSITION        # Step 10: State changed
    NOTIFICATION            # Step 10: Notification sent
    MANUAL_INTERVENTION     # Step 10: Human intervention needed
    SYSTEM_HEALTH           # System health event
```

**Convenience Methods**:

```python
# Log lock acquisition
audit_logger.log_lock_acquired(
    resource_id='payment-service',
    holder_id='op-123',
    lock_scope='SERVICE',
    ttl_seconds=300,
    actor='alice@example.com',
    correlation_id='corr-456'
)

# Log deployment
audit_logger.log_deployment(
    service_name='payment-service',
    version='1.2.3',
    strategy='canary',
    success=True,
    actor='system',
    correlation_id='corr-456'
)

# Log conflict detection
audit_logger.log_conflict_detected(
    service_name='payment-service',
    conflict_type='DEPENDENCY',
    severity='high',
    conflicting_operations=['op-123', 'op-456'],
    blast_radius=5,
    actor='system',
    correlation_id='corr-456'
)
```

**Querying Audit Log**:

```python
# Find all lock operations for payment-service
events = audit_logger.query_events(
    category=ActionCategory.LOCK_OPERATION,
    resource_id='payment-service',
    start_time=datetime.now() - timedelta(hours=24)
)

# Find all operations by specific user
events = audit_logger.query_events(
    actor='alice@example.com',
    start_time=datetime.now() - timedelta(days=7)
)

# Find all critical events in correlation chain
events = audit_logger.query_events(
    correlation_id='corr-456',
    severity=ActionSeverity.CRITICAL
)
```

**Statistics Dashboard**:

```python
stats = audit_logger.get_statistics()
# {
#     'total_events': 1523,
#     'events_by_category': {
#         'DEPLOYMENT': 234,
#         'VERIFICATION': 189,
#         'LOCK_OPERATION': 468,
#         ...
#     },
#     'events_by_severity': {
#         'INFO': 1200,
#         'WARNING': 250,
#         'ERROR': 60,
#         'CRITICAL': 13
#     },
#     'events_per_hour': 63.5,
#     'unique_actors': 15,
#     'unique_services': 42,
#     'hash_chain_valid': True
# }
```

### 3. Dependency-Aware Conflict Detector

**Purpose**: Detect conflicts using RCA dependency graph to find hidden blast radius.

**Implementation**: [conflict_detector.py](conflict_detector.py) (~600 lines)

**Key Features**:
- **7 conflict types**: Direct, Dependency, Downstream, Upstream, Shared Resource, Cascade, Timing
- **Graph-based detection**: Uses Neo4j dependency graph from Step 3 RCA
- **Blast radius calculation**: Transitive closure of affected services
- **Resource grouping**: Tracks services sharing infrastructure
- **Severity-based recommendations**: Block, pause, warn, or delay

**Conflict Types**:

```python
class ConflictType(Enum):
    DIRECT = "direct"                   # Same service, same operation
    DEPENDENCY = "dependency"           # Dependent service affected
    DOWNSTREAM = "downstream"           # Downstream service affected
    UPSTREAM = "upstream"               # Upstream service affected
    SHARED_RESOURCE = "shared_resource" # Services share DB/cache/queue
    CASCADE = "cascade"                 # Could trigger cascading changes
    TIMING = "timing"                   # Operations too close in time
```

**Example: Hidden Conflict Detection**

```
Scenario:
- Operation A: Deploy payment-service v1.2.3
- Operation B: Deploy user-service v2.0.0

Direct Check: No conflict (different services) ✅

Dependency Check:
  - user-service → payment-service (calls payment API)
  - Conflict! User-service change may break payment integration ⚠️

Shared Resource Check:
  - Both services use postgres_primary database
  - Conflict! Schema changes could impact both ⚠️

Result: CONFLICT DETECTED
  Type: DEPENDENCY + SHARED_RESOURCE
  Severity: HIGH
  Blast Radius: 5 services (user, payment, order, shipping, invoice)
  Recommendation: Pause for human review
```

**Resource Groups** (configured in config.yaml):

```yaml
resource_groups:
  postgres_primary:
    - payment-service
    - user-service
    - order-service
  
  redis_cache:
    - user-service
    - session-service
    - auth-service
  
  kafka_orders:
    - order-service
    - inventory-service
    - shipping-service
```

**Graph Traversal** (finding downstream services):

```cypher
-- Neo4j query to find all downstream dependencies
MATCH (source:Service {name: $service_name})-[:DEPENDS_ON*1..3]->(dep:Service)
RETURN COLLECT(DISTINCT dep.name) as downstream_services
```

**Blast Radius Calculation**:

```python
blast_radius = (
    len(directly_affected_services) * 1.0 +
    len(downstream_services) * 0.5 +
    len(shared_resource_services) * 0.8 +
    len(upstream_services) * 0.3
)
```

### 4. Safety Gate Checker

**Purpose**: Pre-action validation to prevent unsafe operations.

**Implementation**: [safety_gate_checker.py](safety_gate_checker.py) (~150 lines)

**Key Features**:
- **6 safety gates**: Error budget, blast radius, recent failures, cooldown, resource capacity, incident rate
- **Configurable thresholds**: All thresholds configured in config.yaml
- **Pass/fail reporting**: Clear reasons for gate failures

**Safety Gates**:

```python
class SafetyGateType(Enum):
    ERROR_BUDGET = "error_budget"           # Check error budget not exhausted
    BLAST_RADIUS = "blast_radius"           # Check estimated impact acceptable
    RECENT_FAILURES = "recent_failures"     # Check recent failure rate
    COOLDOWN = "cooldown"                   # Check time since last operation
    RESOURCE_CAPACITY = "resource_capacity" # Check system capacity headroom
    INCIDENT_RATE = "incident_rate"         # Check current incident rate
```

**Error Budget Gate**:

```python
# SLO: 99.9% uptime = 0.1% error budget
# Current error rate: 0.5%
# Max allowed: 2.0%
# Status: ✅ PASS (within budget)

if current_error_budget_pct > max_error_budget_pct:
    return SafetyGateResult(
        gate_type=SafetyGateType.ERROR_BUDGET,
        passed=False,
        reason=f"Error budget exhausted: {current_error_budget_pct}% > {max_error_budget_pct}%"
    )
```

**Blast Radius Gate**:

```python
# Max blast radius: 20% of services (8 out of 42 services)
# Estimated impact: 5 services (12%)
# Status: ✅ PASS (within limit)

if estimated_blast_radius > max_blast_radius_pct:
    return SafetyGateResult(
        gate_type=SafetyGateType.BLAST_RADIUS,
        passed=False,
        reason=f"Blast radius too large: {estimated_blast_radius}% > {max_blast_radius_pct}%"
    )
```

**Cooldown Gate**:

```python
# Min cooldown: 5 minutes (300 seconds)
# Time since last operation: 2 minutes (120 seconds)
# Status: ❌ FAIL (too soon)

if time_since_last_op < min_cooldown_seconds:
    return SafetyGateResult(
        gate_type=SafetyGateType.COOLDOWN,
        passed=False,
        reason=f"Cooldown not satisfied: {time_since_last_op}s < {min_cooldown_seconds}s"
    )
```

### 5. Concurrency State Machine

**Purpose**: Track operation states with human override capability.

**Implementation**: [concurrency_state_machine.py](concurrency_state_machine.py) (~150 lines)

**Key Features**:
- **9 states**: Including PAUSED_FOR_HUMAN_REVIEW for responsible automation
- **Transition validation**: Enforces allowed state transitions
- **Audit history**: Tracks all state transitions with timestamps
- **Human override**: pause_for_review() and resume_from_pause() methods

**States**:

```python
class ConcurrencyState(Enum):
    INIT = "init"                               # Operation initialized
    LOCKED = "locked"                           # Lock acquired
    SAFETY_CHECK = "safety_check"               # Safety gates being checked
    IN_PROGRESS = "in_progress"                 # Operation executing
    PAUSED_FOR_HUMAN_REVIEW = "paused_for_human_review"  # Waiting for human approval
    COMPLETED = "completed"                     # Operation successful (terminal)
    FAILED = "failed"                           # Operation failed (terminal)
    ROLLED_BACK = "rolled_back"                 # Rolled back after failure (terminal)
    CANCELLED = "cancelled"                     # Cancelled by user (terminal)
```

**State Transition Rules**:

```python
ALLOWED_TRANSITIONS = {
    ConcurrencyState.INIT: [
        ConcurrencyState.LOCKED,
        ConcurrencyState.FAILED,
        ConcurrencyState.CANCELLED
    ],
    ConcurrencyState.LOCKED: [
        ConcurrencyState.SAFETY_CHECK,
        ConcurrencyState.FAILED,
        ConcurrencyState.CANCELLED
    ],
    ConcurrencyState.SAFETY_CHECK: [
        ConcurrencyState.IN_PROGRESS,
        ConcurrencyState.PAUSED_FOR_HUMAN_REVIEW,
        ConcurrencyState.FAILED,
        ConcurrencyState.CANCELLED
    ],
    ConcurrencyState.IN_PROGRESS: [
        ConcurrencyState.COMPLETED,
        ConcurrencyState.PAUSED_FOR_HUMAN_REVIEW,
        ConcurrencyState.FAILED,
        ConcurrencyState.ROLLED_BACK
    ],
    ConcurrencyState.PAUSED_FOR_HUMAN_REVIEW: [
        ConcurrencyState.IN_PROGRESS,  # Resume after approval
        ConcurrencyState.FAILED,
        ConcurrencyState.CANCELLED
    ],
    # Terminal states (no transitions allowed)
    ConcurrencyState.COMPLETED: [],
    ConcurrencyState.FAILED: [ConcurrencyState.ROLLED_BACK],
    ConcurrencyState.ROLLED_BACK: [],
    ConcurrencyState.CANCELLED: []
}
```

**Human Override Flow**:

```python
# Pause for human review
state_machine.pause_for_review(
    reason='High blast radius detected (15 services)',
    paused_by='alice@example.com',
    severity='high'
)
# State: IN_PROGRESS → PAUSED_FOR_HUMAN_REVIEW

# Human reviews and approves
state_machine.resume_from_pause(
    resumed_by='bob@example.com',
    approval_id='APPROVE-12345',
    notes='Reviewed dependency graph, safe to proceed'
)
# State: PAUSED_FOR_HUMAN_REVIEW → IN_PROGRESS
```

**Audit History**:

```python
history = state_machine.get_history()
# [
#     StateTransition(
#         from_state='init',
#         to_state='locked',
#         timestamp='2024-01-15T10:30:00Z',
#         actor='system',
#         metadata={'lock_scope': 'SERVICE'}
#     ),
#     StateTransition(
#         from_state='locked',
#         to_state='safety_check',
#         timestamp='2024-01-15T10:30:05Z',
#         actor='system',
#         metadata={}
#     ),
#     ...
# ]
```

### 6. Multi-Channel Notifier

**Purpose**: Keep stakeholders informed via Slack, email, PagerDuty, etc.

**Implementation**: [notifier.py](notifier.py) (~200 lines)

**Key Features**:
- **4 channels**: Slack, email, PagerDuty, Microsoft Teams
- **Severity-based routing**: Route notifications based on severity
- **Template-based messages**: Consistent message formatting
- **Delivery tracking**: Track notification delivery status

**Notification Channels**:

```python
class NotificationChannel(Enum):
    SLACK = "slack"
    EMAIL = "email"
    PAGERDUTY = "pagerduty"
    TEAMS = "teams"
```

**Severity-Based Routing** (from config.yaml):

```yaml
routing:
  INFO:
    channels: [slack]
    throttle_minutes: 5
  
  WARNING:
    channels: [slack, email]
    throttle_minutes: 2
  
  ERROR:
    channels: [slack, email, pagerduty]
    throttle_minutes: 0
  
  CRITICAL:
    channels: [slack, email, pagerduty, phone]
    throttle_minutes: 0
    escalate_after_minutes: 15
```

**Example Notifications**:

```python
# INFO: Lock acquired
notifier.send(
    title='Lock Acquired',
    message='Lock acquired for payment-service',
    severity=NotificationSeverity.INFO
)
# Sent to: Slack

# WARNING: Conflict detected
notifier.send(
    title='Conflict Detected',
    message='Dependency conflict: user-service → payment-service',
    severity=NotificationSeverity.WARNING
)
# Sent to: Slack, Email

# ERROR: Safety gate failed
notifier.send(
    title='Safety Gate Failed',
    message='Error budget exhausted: 2.5% > 2.0%',
    severity=NotificationSeverity.ERROR
)
# Sent to: Slack, Email, PagerDuty

# CRITICAL: Operation failed
notifier.send(
    title='Operation Failed',
    message='Deployment failed - manual rollback required',
    severity=NotificationSeverity.CRITICAL
)
# Sent to: Slack, Email, PagerDuty, Phone
# Escalated after 15 minutes if no response
```

### 7. Concurrency Orchestrator

**Purpose**: Central coordinator integrating all Step 10 components.

**Implementation**: [concurrency_orchestrator.py](concurrency_orchestrator.py) (~800 lines)

**Key Features**:
- **Unified interface**: Single entry point for all operations
- **Complete workflow**: Handles entire operation lifecycle
- **Integration**: Connects to Steps 8 (Deployment) and 9 (Verification)
- **Error handling**: Comprehensive error handling and recovery

**Main Workflow**:

```python
async def execute_operation(
    operation_type: OperationType,
    service_name: str,
    operation_data: Dict[str, Any],
    correlation_id: Optional[str] = None,
    actor: str = "system"
) -> ExecutionResult:
    """
    Execute operation with full concurrency control.
    
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
    """
```

**Example Usage**:

```python
orchestrator = ConcurrencyOrchestrator(config)

# Deploy new version
result = await orchestrator.execute_operation(
    operation_type=OperationType.DEPLOYMENT,
    service_name='payment-service',
    operation_data={
        'version': '1.2.3',
        'strategy': 'canary',
        'estimated_duration_minutes': 10
    },
    actor='alice@example.com'
)

# Check result
if result.result == OperationResult.SUCCESS:
    print(f"✅ Deployment successful in {result.duration_seconds}s")
elif result.result == OperationResult.PAUSED_FOR_REVIEW:
    print(f"⏸️  Paused for human review: {result.pause_reason}")
elif result.result == OperationResult.BLOCKED_BY_CONFLICT:
    print(f"🛑 Blocked by conflict: {result.conflicts_detected}")
```

## Advanced Features

### 1. Dependency-Aware Conflict Detection

**Traditional conflict detection** only checks if same service is being modified:

```
Operation A: Deploy payment-service ✅
Operation B: Deploy user-service ✅  (No conflict - different services)
```

**Problem**: Misses hidden dependencies!

**Dependency-aware detection** uses RCA graph to find hidden conflicts:

```
Operation A: Deploy payment-service
Operation B: Deploy user-service

Check dependency graph:
  user-service → payment-service (API dependency)

Result: ⚠️ CONFLICT DETECTED
  Type: DEPENDENCY
  Reason: user-service depends on payment-service
  Risk: User-service change may break payment integration
  Blast Radius: 5 services affected
  Recommendation: Coordinate deployment or pause for review
```

**Implementation**:

```python
def _check_dependency_conflicts(self, operation_id: str) -> Optional[ConflictResult]:
    """Check for conflicts based on service dependencies"""
    
    op = self._ongoing_operations[operation_id]
    service_name = op.service_name
    
    # Query Neo4j for service dependencies
    with self.neo4j_driver.session() as session:
        result = session.run("""
            MATCH (source:Service {name: $service_name})-[:DEPENDS_ON]->(dep:Service)
            RETURN dep.name as dependency
        """, service_name=service_name)
        
        dependencies = [record['dependency'] for record in result]
    
    # Check if any dependency has ongoing operation
    for other_op_id, other_op in self._ongoing_operations.items():
        if other_op_id == operation_id:
            continue
        
        if other_op.service_name in dependencies:
            return ConflictResult(
                has_conflict=True,
                conflict_type=ConflictType.DEPENDENCY,
                severity='high',
                conflicting_operations=[operation_id, other_op_id],
                affected_services=[service_name, other_op.service_name],
                blast_radius=self._calculate_blast_radius(service_name),
                explanation=f"{service_name} depends on {other_op.service_name} which has ongoing {other_op.operation_type.value}",
                recommendation="Coordinate deployment or pause for human review"
            )
    
    return None
```

**Benefits**:
- Detects hidden conflicts traditional methods miss
- Uses real dependency data from RCA graph
- Calculates accurate blast radius
- Prevents cascading failures

### 2. Deadlock Prevention via Lock Ordering

**Deadlock scenario** (without lock ordering):

```
Thread A:                       Thread B:
1. Lock payment-service ✅      1. Lock postgres-db ✅
2. Wait for postgres-db 🔒      2. Wait for payment-service 🔒
   (Thread B holds it)              (Thread A holds it)
   
Result: DEADLOCK! Both threads wait forever
```

**Solution: Lock Ordering Rules**

Define global lock hierarchy:

```python
class LockScope(Enum):
    SYSTEM = 1      # System-wide (DB, infra)
    SERVICE = 2     # Service-level
    INCIDENT = 3    # Incident-specific
    DEPLOYMENT = 4  # Deployment-specific
```

**Rule**: ALWAYS acquire locks in order (SYSTEM → SERVICE → INCIDENT → DEPLOYMENT)

**Corrected scenario**:

```
Thread A:                       Thread B:
1. Lock postgres-db ✅          1. Lock postgres-db 🔒 (WAIT for A)
   (SYSTEM scope)
2. Lock payment-service ✅      2. Lock postgres-db ✅
3. Release all                     (A released)
                                3. Lock payment-service ✅
                                4. Release all

Result: ✅ NO DEADLOCK! Operations execute sequentially
```

**Implementation**:

```python
def _validate_lock_ordering(
    self,
    resource_id: str,
    scope: LockScope,
    holder_id: str
) -> bool:
    """
    Validate that locks are acquired in proper order.
    
    Rule: Must acquire locks in order: SYSTEM → SERVICE → INCIDENT → DEPLOYMENT
    """
    # Get all locks currently held by this holder
    held_locks = [
        lock for lock in self._lock_registry.values()
        if lock.holder_id == holder_id
    ]
    
    # Check if any held lock has higher scope (lower priority number)
    for held_lock in held_locks:
        if held_lock.scope.value > scope.value:
            logger.error(
                f"❌ LOCK ORDERING VIOLATION: Attempting to acquire {scope.name} lock "
                f"while holding {held_lock.scope.name} lock. "
                f"Must acquire locks in order: SYSTEM → SERVICE → INCIDENT → DEPLOYMENT"
            )
            return False
    
    return True
```

**Additional Rule: Alphabetical Ordering Within Same Scope**

Within same scope, acquire locks alphabetically to prevent circular waits:

```
Thread A:                           Thread B:
1. Lock payment-service ✅          1. Lock payment-service 🔒 (WAIT)
2. Lock user-service ✅             2. ...
3. Release all                      3. Lock payment-service ✅
                                    4. Lock user-service ✅

Result: ✅ NO DEADLOCK! Alphabetical ordering ensures consistent order
```

**Documented Deadlock Scenarios** (see distributed_lock_manager.py):

1. **Circular Dependencies**
2. **Inconsistent Lock Ordering**
3. **Long-Running Operations**
4. **Lock Leaks**
5. **Priority Inversion**

### 3. Human Override State (PAUSED_FOR_HUMAN_REVIEW)

**Problem**: Fully automated systems can cause damage when operating in unexpected conditions.

**Solution**: Responsible automation with human-in-the-loop capability.

**When to Pause for Human Review**:

1. **High-risk conflicts**: Dependency conflicts affecting many services
2. **Safety gate failures**: Error budget exhausted, blast radius too large
3. **Multiple failures**: Repeated failures indicate systemic issue
4. **Unknown conditions**: Situations not covered by automation rules

**PAUSED_FOR_HUMAN_REVIEW State**:

```python
class ConcurrencyState(Enum):
    # ... other states ...
    PAUSED_FOR_HUMAN_REVIEW = "paused_for_human_review"  # Wait for human approval
```

**Pause Flow**:

```python
# System detects high-risk condition
if conflict.severity == 'high' and conflict.blast_radius > 10:
    state_machine.pause_for_review(
        reason=f"High blast radius: {conflict.blast_radius} services affected",
        paused_by='system',
        severity='high'
    )
    
    # Notify stakeholders
    notifier.send(
        title='Human Review Required',
        message=f'Operation paused: {reason}\n\n'
                f'Blast Radius: {conflict.blast_radius} services\n'
                f'Please review and approve/reject.',
        severity=NotificationSeverity.WARNING,
        channels=[NotificationChannel.SLACK, NotificationChannel.EMAIL]
    )
```

**Resume Flow**:

```python
# Human reviews and approves
state_machine.resume_from_pause(
    resumed_by='alice@example.com',
    approval_id='APPROVE-12345',
    notes='Reviewed dependency graph. Safe to proceed - teams coordinated.'
)

# Continue operation
execute_deployment(...)
```

**Benefits**:
- Prevents automation from causing large-scale damage
- Maintains human oversight for high-risk operations
- Builds trust in automation system
- Provides learning opportunity (analyze paused cases)

**Escalation Policy** (from config.yaml):

```yaml
escalation:
  # Level 1: On-call engineer (15 min)
  level_1:
    timeout_minutes: 15
    notify: [slack, email]
  
  # Level 2: SRE lead (30 min)
  level_2:
    timeout_minutes: 30
    notify: [slack, email, pagerduty]
  
  # Level 3: Engineering manager (60 min)
  level_3:
    timeout_minutes: 60
    notify: [slack, email, pagerduty, phone]
```

## Workflows

### Workflow 1: Successful Deployment

```
[User] alice@example.com triggers deployment of payment-service v1.2.3
   │
   ▼
[Orchestrator] Generate operation ID: op-abc123
   │
   ▼
[State Machine] INIT
   │
   ▼
[Conflict Detector] Register operation
   │
   ▼
[Conflict Detector] Check dependency graph
   │
   ├─► Neo4j query: MATCH (s:Service {name: 'payment-service'})-[:DEPENDS_ON]->(dep)
   │
   └─► Result: No ongoing operations on dependencies ✅
   │
   ▼
[Lock Manager] Acquire lock (scope=SERVICE)
   │
   ├─► Check lock ordering: No locks held ✅
   ├─► Redis SET payment-service:op-abc123 EX 300 NX
   └─► Lock acquired ✅
   │
   ▼
[State Machine] INIT → LOCKED
   │
   ▼
[Audit Logger] log_lock_acquired(payment-service, op-abc123, SERVICE)
   │
   ▼
[State Machine] LOCKED → SAFETY_CHECK
   │
   ▼
[Safety Gate Checker] Check all gates
   │
   ├─► Error Budget: 0.5% < 2.0% ✅
   ├─► Blast Radius: 12% < 20% ✅
   ├─► Recent Failures: 1 < 3 ✅
   ├─► Cooldown: 350s > 300s ✅
   ├─► Resource Capacity: 35% > 20% ✅
   └─► Incident Rate: 2/hr < 5/hr ✅
   │
   ▼
[State Machine] SAFETY_CHECK → IN_PROGRESS
   │
   ▼
[Audit Logger] log_safety_gate_result(all_passed=True)
   │
   ▼
[Deployment Engine] Execute canary deployment
   │
   ├─► Deploy v1.2.3 to 10% of instances
   ├─► Wait 5 minutes
   ├─► Check health metrics
   └─► Deploy to 100% ✅
   │
   ▼
[State Machine] IN_PROGRESS → COMPLETED
   │
   ▼
[Audit Logger] log_deployment(payment-service, v1.2.3, success=True)
   │
   ▼
[Lock Manager] Release lock (payment-service, op-abc123)
   │
   └─► Redis DEL payment-service ✅
   │
   ▼
[Audit Logger] log_lock_released(payment-service, op-abc123)
   │
   ▼
[Notifier] Send notification (Slack)
   │
   └─► "✅ Deployment Successful: payment-service v1.2.3 (Duration: 245s)"
   │
   ▼
[Orchestrator] Return ExecutionResult(SUCCESS)
```

### Workflow 2: Conflict Detected - Paused for Review

```
[System] Auto-healing detects payment-service incident, starts auto-fix (op-def456)
   │
   ▼
[Orchestrator] Generate operation ID: op-def456
   │
   ▼
[State Machine] INIT
   │
   ▼
[Conflict Detector] Register operation (DEPLOYMENT, payment-service)
   │
   ▼
[Conflict Detector] Check ongoing operations
   │
   ├─► Found: op-abc123 (DEPLOYMENT, payment-service) - Still in progress!
   │
   └─► CONFLICT: DIRECT conflict (same service, same operation type)
   │
   ▼
[Audit Logger] log_conflict_detected(
                   conflict_type=DIRECT,
                   severity=critical,
                   conflicting_operations=[op-abc123, op-def456]
               )
   │
   ▼
[Notifier] Send notification (Slack, PagerDuty)
   │
   └─► "🛑 CONFLICT DETECTED: payment-service"
       "Type: DIRECT"
       "Severity: CRITICAL"
       "Operation op-def456 blocked - op-abc123 still in progress"
   │
   ▼
[State Machine] INIT → FAILED
   │
   ▼
[Orchestrator] Return ExecutionResult(BLOCKED_BY_CONFLICT)
   │
   └─► User sees: "Operation blocked - payment-service has ongoing deployment"
```

### Workflow 3: Safety Gate Failed - Paused for Review

```
[User] bob@example.com triggers deployment of user-service v2.0.0
   │
   ▼
[Orchestrator] Generate operation ID: op-ghi789
   │
   ▼
[State Machine] INIT
   │
   ▼
[Conflict Detector] No conflicts ✅
   │
   ▼
[Lock Manager] Acquire lock ✅
   │
   ▼
[State Machine] INIT → LOCKED → SAFETY_CHECK
   │
   ▼
[Safety Gate Checker] Check all gates
   │
   ├─► Error Budget: 2.5% > 2.0% ❌ FAIL
   ├─► Blast Radius: 15% < 20% ✅
   └─► (Other gates...)
   │
   ▼
[Audit Logger] log_safety_gate_result(
                   gates_passed=False,
                   failed_gates=['error_budget']
               )
   │
   ▼
[State Machine] SAFETY_CHECK → PAUSED_FOR_HUMAN_REVIEW
   │
   ▼
[State Machine] pause_for_review(
                   reason='Error budget exhausted: 2.5% > 2.0%',
                   paused_by='system',
                   severity='high'
               )
   │
   ▼
[Audit Logger] log_manual_intervention(
                   reason='Error budget exhausted',
                   severity='high'
               )
   │
   ▼
[Notifier] Send notification (Slack, Email, PagerDuty)
   │
   └─► "⏸️  HUMAN REVIEW REQUIRED: user-service"
       "Reason: Error budget exhausted (2.5% > 2.0%)"
       "Action: Review error budget and approve/reject deployment"
       "[Approve] [Reject]"
   │
   ▼
[Human] alice@example.com reviews
   │
   ├─► Checks error budget dashboard
   ├─► Sees: Most errors from payment-service (not user-service)
   └─► Decision: Safe to proceed
   │
   ▼
[Human] Clicks [Approve] with approval ID: APPROVE-99887
   │
   ▼
[State Machine] resume_from_pause(
                   resumed_by='alice@example.com',
                   approval_id='APPROVE-99887',
                   notes='Errors from different service - safe to deploy'
               )
   │
   ▼
[State Machine] PAUSED_FOR_HUMAN_REVIEW → IN_PROGRESS
   │
   ▼
[Deployment Engine] Execute deployment
   │
   └─► (Deployment continues normally...)
```

### Workflow 4: Deadlock Prevention

```
[Operation A] Deploy payment-service (requires DB schema change)
[Operation B] Deploy user-service (requires DB schema change)

--- Without Lock Ordering (DEADLOCK) ---

Thread A:                          Thread B:
1. Lock payment-service ✅         1. Lock user-service ✅
2. Try lock postgres-db 🔒         2. Try lock postgres-db 🔒
   (Thread B holds it)                (Thread A holds it)
   
Result: ⚠️ DEADLOCK

--- With Lock Ordering (NO DEADLOCK) ---

Thread A:                          Thread B:
1. Try lock postgres-db ✅         1. Try lock postgres-db 🔒
   (scope=SYSTEM)                     (WAIT - Thread A holds it)
2. Lock payment-service ✅         2. ...
   (scope=SERVICE)
3. Execute deployment
4. Release postgres-db
5. Release payment-service
                                   3. Lock postgres-db ✅
                                      (Thread A released)
                                   4. Lock user-service ✅
                                   5. Execute deployment
                                   6. Release all

Result: ✅ NO DEADLOCK - Sequential execution
```

**Lock Ordering Validation**:

```
[Operation] Trying to acquire SERVICE lock while holding DEPLOYMENT lock
   │
   ▼
[Lock Manager] _validate_lock_ordering()
   │
   ├─► Check held locks: DEPLOYMENT (scope=4)
   ├─► Check requested lock: SERVICE (scope=2)
   └─► VIOLATION: scope(4) > scope(2)
   │
   ▼
[Lock Manager] ❌ REJECT lock acquisition
   │
   ▼
[Audit Logger] log_lock_failed(
                   reason='lock_ordering_violation',
                   details='Cannot acquire SERVICE lock while holding DEPLOYMENT lock'
               )
   │
   ▼
[Notifier] Send notification (Slack, PagerDuty)
   │
   └─► "🚨 LOCK ORDERING VIOLATION"
       "Must acquire locks in order: SYSTEM → SERVICE → INCIDENT → DEPLOYMENT"
       "Fix code to acquire SERVICE lock before DEPLOYMENT lock"
```

## Configuration

Complete configuration in [concurrency_config.yaml](concurrency_config.yaml).

### Key Configuration Sections

#### 1. Distributed Locking

```yaml
locking:
  backend: redis  # redis | etcd | kubernetes | file
  
  redis:
    host: localhost
    port: 6379
  
  default_ttl_seconds: 300
  wait_timeout_seconds: 30
  
  lock_ordering:
    SYSTEM: 1
    SERVICE: 2
    INCIDENT: 3
    DEPLOYMENT: 4
```

#### 2. Conflict Detection

```yaml
conflict_detection:
  dependency_aware: true
  
  neo4j:
    uri: bolt://localhost:7687
    user: neo4j
    password: neo4j_password
  
  conflict_types:
    DIRECT:
      severity: critical
      action: block
    DEPENDENCY:
      severity: high
      action: pause_for_review
  
  resource_groups:
    postgres_primary:
      - payment-service
      - user-service
```

#### 3. Safety Gates

```yaml
safety_gates:
  error_budget:
    enabled: true
    max_error_budget_pct: 2.0
  
  blast_radius:
    enabled: true
    max_blast_radius_pct: 20.0
  
  cooldown:
    enabled: true
    min_seconds_between_ops: 300
```

#### 4. Human Override

```yaml
human_override:
  enabled: true
  
  pause_conditions:
    - conflict_severity: [high, critical]
    - safety_gate_failed: [error_budget, blast_radius]
  
  escalation:
    level_1:
      timeout_minutes: 15
      notify: [slack, email]
    level_2:
      timeout_minutes: 30
      notify: [slack, email, pagerduty]
```

#### 5. Notifications

```yaml
notifications:
  enabled_channels:
    - slack
    - email
  
  slack:
    webhook_url: https://hooks.slack.com/services/YOUR/WEBHOOK/URL
    channel: "#sre-alerts"
  
  routing:
    CRITICAL:
      channels: [slack, email, pagerduty]
      escalate_after_minutes: 15
```

## Integration

### Integration with Step 8: Deployment Engine

**Before** (without concurrency control):

```python
# Step 8: Deployment Engine
def deploy(service_name, version):
    # No checks - just deploy!
    execute_deployment(service_name, version)
```

**After** (with concurrency control):

```python
# Step 8: Deployment Engine (integrated with Step 10)
async def deploy(service_name, version):
    # Use orchestrator for safe deployment
    result = await orchestrator.execute_operation(
        operation_type=OperationType.DEPLOYMENT,
        service_name=service_name,
        operation_data={
            'version': version,
            'strategy': 'canary'
        }
    )
    
    if result.result == OperationResult.SUCCESS:
        return DeploymentResult.SUCCESS
    elif result.result == OperationResult.BLOCKED_BY_CONFLICT:
        return DeploymentResult.BLOCKED
    elif result.result == OperationResult.PAUSED_FOR_REVIEW:
        return DeploymentResult.PAUSED
```

### Integration with Step 9: Verification & Rollback

**Before** (without concurrency control):

```python
# Step 9: Verification Engine
def verify(service_name):
    # No checks - just verify!
    run_health_checks(service_name)
```

**After** (with concurrency control):

```python
# Step 9: Verification Engine (integrated with Step 10)
async def verify(service_name):
    # Use orchestrator for safe verification
    result = await orchestrator.execute_operation(
        operation_type=OperationType.VERIFICATION,
        service_name=service_name,
        operation_data={
            'verification_type': 'health_check'
        }
    )
    
    return result.result == OperationResult.SUCCESS
```

### Integration Example: End-to-End Auto-Healing

```python
# Complete auto-healing flow with concurrency control

# Step 1: Incident detected
incident = detect_incident()

# Step 2-6: RCA, localization, fix planning, patch generation
# (Handled by Steps 2-6)

# Step 7: Safety gates (integrated into Step 10)
# (No separate call needed)

# Step 8: Deploy patch (with concurrency control)
result = await orchestrator.execute_operation(
    operation_type=OperationType.DEPLOYMENT,
    service_name=incident.service_name,
    operation_data={
        'version': patch.version,
        'strategy': 'canary',
        'correlation_id': incident.id
    },
    actor='auto-healing-system'
)

if result.result == OperationResult.PAUSED_FOR_REVIEW:
    # Human review needed - send notification
    notify_oncall(f"Auto-healing paused: {result.pause_reason}")
    wait_for_approval()

# Step 9: Verify deployment (with concurrency control)
verify_result = await orchestrator.execute_operation(
    operation_type=OperationType.VERIFICATION,
    service_name=incident.service_name,
    operation_data={
        'verification_type': 'comprehensive',
        'correlation_id': incident.id
    },
    actor='auto-healing-system'
)

if verify_result.result != OperationResult.SUCCESS:
    # Verification failed - rollback (with concurrency control)
    rollback_result = await orchestrator.execute_operation(
        operation_type=OperationType.ROLLBACK,
        service_name=incident.service_name,
        operation_data={
            'to_version': incident.previous_version,
            'correlation_id': incident.id
        },
        actor='auto-healing-system'
    )
```

## Deployment

### Development Environment

```bash
# 1. Install dependencies
pip install redis neo4j elasticsearch pyyaml

# 2. Start local services (optional - file-based fallback available)
docker-compose up -d redis neo4j elasticsearch

# 3. Configure
cp concurrency_config.yaml.example concurrency_config.yaml
vim concurrency_config.yaml  # Set development mode

# 4. Test individual components
python distributed_lock_manager.py
python audit_logger.py
python conflict_detector.py

# 5. Test orchestrator
python concurrency_orchestrator.py
```

### Production Environment

```bash
# 1. Use production backends
# - Redis Cluster (for distributed locking)
# - Neo4j (from Step 3 RCA)
# - Elasticsearch (for audit logging)

# 2. Configure production settings
vim concurrency_config.yaml
# Set:
#   locking.backend: redis
#   locking.redis.host: redis-cluster.prod
#   conflict_detection.neo4j.uri: bolt://neo4j-prod:7687
#   audit_logging.backends.elasticsearch.enabled: true
#   notifications.enabled_channels: [slack, email, pagerduty]

# 3. Deploy as systemd service
sudo cp concurrency-orchestrator.service /etc/systemd/system/
sudo systemctl enable concurrency-orchestrator
sudo systemctl start concurrency-orchestrator

# 4. Monitor
sudo journalctl -u concurrency-orchestrator -f

# 5. Verify hash chain integrity
python -c "from audit_logger import AuditLogger; logger = AuditLogger('/var/log/concurrency_audit.jsonl'); print(logger.verify_hash_chain())"
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: concurrency-orchestrator
spec:
  replicas: 3
  selector:
    matchLabels:
      app: concurrency-orchestrator
  template:
    metadata:
      labels:
        app: concurrency-orchestrator
    spec:
      containers:
      - name: orchestrator
        image: your-registry/concurrency-orchestrator:latest
        env:
        - name: REDIS_HOST
          value: redis-cluster
        - name: NEO4J_URI
          value: bolt://neo4j:7687
        - name: ELASTICSEARCH_URL
          value: http://elasticsearch:9200
        - name: CONFIG_FILE
          value: /etc/concurrency/config.yaml
        volumeMounts:
        - name: config
          mountPath: /etc/concurrency
        - name: audit-logs
          mountPath: /var/log
      volumes:
      - name: config
        configMap:
          name: concurrency-config
      - name: audit-logs
        persistentVolumeClaim:
          claimName: audit-logs-pvc
```

## Troubleshooting

### Issue 1: Lock Acquisition Timeout

**Symptoms**:
- Operations fail with "Failed to acquire lock"
- Logs show "Waiting for lock..." timeout

**Diagnosis**:

```bash
# Check active locks
python -c "
from distributed_lock_manager import DistributedLockManager
mgr = DistributedLockManager()
print(mgr.get_active_locks())
"

# Check Redis (if using Redis backend)
redis-cli
> KEYS concurrency:lock:*
> GET concurrency:lock:payment-service
```

**Solutions**:

1. **Stale lock**: Lock holder died without releasing

```python
# Force release stale lock
lock_manager.force_release_all(older_than_seconds=600)
```

2. **Long-running operation**: Increase TTL

```yaml
# concurrency_config.yaml
locking:
  default_ttl_seconds: 600  # Increase from 300 to 600
```

3. **High contention**: Increase wait timeout

```yaml
locking:
  wait_timeout_seconds: 60  # Increase from 30 to 60
```

### Issue 2: False Conflict Detection

**Symptoms**:
- Operations blocked unnecessarily
- Logs show conflicts but services unrelated

**Diagnosis**:

```python
# Check dependency graph
from neo4j import GraphDatabase

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))
with driver.session() as session:
    result = session.run("""
        MATCH (s1:Service {name: 'payment-service'})-[:DEPENDS_ON]->(s2:Service)
        RETURN s2.name
    """)
    print([r['s2.name'] for r in result])
```

**Solutions**:

1. **Outdated dependency graph**: Refresh graph from Step 3 RCA

```bash
# Re-run dependency discovery
python step3_rca_engine.py --refresh-dependencies
```

2. **Incorrect resource groups**: Update config

```yaml
# concurrency_config.yaml
conflict_detection:
  resource_groups:
    postgres_primary:
      - payment-service
      - user-service
      # Remove: order-service (uses different DB)
```

3. **Overly sensitive conflict detection**: Adjust conflict types

```yaml
conflict_detection:
  conflict_types:
    DOWNSTREAM:
      severity: medium  # Change from high to medium
      action: warn       # Change from pause_for_review to warn
```

### Issue 3: Safety Gates Always Failing

**Symptoms**:
- All operations blocked by safety gates
- Error budget gate consistently fails

**Diagnosis**:

```python
# Check current error budget
from safety_gate_checker import SafetyGateChecker

checker = SafetyGateChecker(config)
gates_passed, results = checker.check_all_gates('payment-service', 'deployment', 5)

for result in results:
    print(f"{result.gate_type.value}: {'PASS' if result.passed else 'FAIL'}")
    if not result.passed:
        print(f"  Reason: {result.reason}")
        print(f"  Details: {result.details}")
```

**Solutions**:

1. **Error budget exhausted**: Fix underlying errors first

```bash
# Check error rate
kubectl top pods payment-service
kubectl logs payment-service | grep ERROR | wc -l
```

2. **Threshold too strict**: Adjust thresholds

```yaml
safety_gates:
  error_budget:
    max_error_budget_pct: 5.0  # Increase from 2.0 to 5.0 (temporarily)
```

3. **Incorrect calculation**: Check time window

```yaml
safety_gates:
  error_budget:
    check_window_hours: 24  # Check last 24 hours (not 1 hour)
```

### Issue 4: Hash Chain Verification Failed

**Symptoms**:
- Audit log reports "Hash chain verification failed"
- Tamper detection triggered

**Diagnosis**:

```python
# Verify hash chain
from audit_logger import AuditLogger

logger = AuditLogger('/var/log/concurrency_audit.jsonl')
is_valid = logger.verify_hash_chain()

if not is_valid:
    # Find tampered event
    events = logger._load_events_from_file()
    for i in range(1, len(events)):
        expected_hash = logger._compute_hash(events[i-1], events[i])
        if events[i].event_hash != expected_hash:
            print(f"Tampered event: {i}")
            print(events[i])
```

**Solutions**:

1. **File corruption**: Restore from backup

```bash
# Restore audit log from backup
cp /var/log/concurrency_audit.jsonl.backup /var/log/concurrency_audit.jsonl
```

2. **Clock skew**: Sync system clocks

```bash
# Sync NTP
sudo ntpdate -s time.nist.gov
```

3. **Manual edit**: Rebuild hash chain

```python
# Rebuild hash chain (CAUTION: Only if you know file was manually edited)
from audit_logger import AuditLogger

logger = AuditLogger('/var/log/concurrency_audit.jsonl')
logger._rebuild_hash_chain()  # This will recompute all hashes
```

### Issue 5: Notifications Not Sent

**Symptoms**:
- No Slack/email notifications received
- Logs show "Notification sent" but nothing arrives

**Diagnosis**:

```python
# Test notifier directly
from notifier import Notifier, NotificationSeverity

notifier = Notifier({'enabled_channels': ['slack', 'email']})
notifier.send(
    title='Test Notification',
    message='This is a test',
    severity=NotificationSeverity.INFO
)
# Check logs for actual API calls
```

**Solutions**:

1. **Invalid webhook URL**: Check Slack webhook

```bash
# Test Slack webhook manually
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"Test message"}' \
  https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

2. **Email credentials**: Check SMTP settings

```yaml
notifications:
  email:
    smtp_host: smtp.gmail.com
    smtp_port: 587
    smtp_user: alerts@example.com
    smtp_password: your_app_password  # Use app password, not account password
```

3. **Throttling**: Check notification rate limits

```yaml
notifications:
  routing:
    INFO:
      throttle_minutes: 5  # May be blocking too many notifications
```

## Summary

Step 10 provides **enterprise-grade concurrency control** with:

✅ **Distributed Locking**: Prevent race conditions (Redis/etcd/K8s)  
✅ **Deadlock Prevention**: Lock ordering rules + explicit documentation  
✅ **Dependency-Aware Conflicts**: Graph-based detection using RCA  
✅ **Safety Gates**: Pre-action validation (error budget, blast radius)  
✅ **Human Override**: PAUSED_FOR_HUMAN_REVIEW for responsible automation  
✅ **Audit Logging**: Tamper-evident hash chain for compliance  
✅ **Multi-Channel Notifications**: Slack, email, PagerDuty  

This is **Google SRE/Meta/Netflix-level concurrency control** - not just locks, but intelligent coordination with systems thinking, distributed systems maturity, and responsible automation.

---

**Next Step**: [Step 11: Documentation & Demo](../README.md) - Document complete architecture and demonstrate end-to-end self-healing scenario.
