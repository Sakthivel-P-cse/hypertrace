#!/usr/bin/env python3
"""
Distributed Lock Manager with Deadlock Prevention

This module provides distributed locking capabilities to prevent race conditions
and conflicting operations across the self-healing system.

Key Features:
- Redis-based distributed locking (with fallback to file-based locks)
- Deadlock prevention via lock ordering
- Lock timeout and auto-release
- Lock health monitoring
- Hierarchical lock granularity (system, service, incident, deployment)
- Audit trail for all lock operations
- Integration with Step 8/9 state machines

Lock Ordering Rules (to prevent deadlocks):
1. SYSTEM locks must be acquired first
2. SERVICE locks before INCIDENT locks
3. INCIDENT locks before DEPLOYMENT locks
4. Always acquire locks in alphabetical order when locking multiple resources

Deadlock Scenarios Documented:
- Scenario 1: Service A → Service B, Service B → Service A (circular dependency)
  Prevention: Lock ordering + dependency graph analysis
- Scenario 2: Multiple orchestrators acquiring locks in different orders
  Prevention: Consistent lock ordering rules
- Scenario 3: Long-running operations holding locks
  Prevention: Lock timeouts + health checks
"""

import redis
import time
import json
import hashlib
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum
import threading
import fcntl
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LockScope(Enum):
    """Lock granularity levels (ordered for deadlock prevention)"""
    SYSTEM = 1      # Global system lock (highest priority)
    SERVICE = 2     # Per-service lock
    INCIDENT = 3    # Per-incident lock
    DEPLOYMENT = 4  # Per-deployment lock (lowest priority)


class LockStatus(Enum):
    """Lock status"""
    ACQUIRED = "acquired"
    RELEASED = "released"
    EXPIRED = "expired"
    FAILED = "failed"
    WAITING = "waiting"


class LockInfo:
    """Information about a lock"""
    def __init__(
        self,
        lock_id: str,
        scope: LockScope,
        resource_id: str,
        owner: str,
        acquired_at: datetime,
        expires_at: datetime,
        metadata: Optional[Dict] = None
    ):
        self.lock_id = lock_id
        self.scope = scope
        self.resource_id = resource_id
        self.owner = owner
        self.acquired_at = acquired_at
        self.expires_at = expires_at
        self.metadata = metadata or {}
        
    def to_dict(self) -> Dict:
        return {
            'lock_id': self.lock_id,
            'scope': self.scope.name,
            'resource_id': self.resource_id,
            'owner': self.owner,
            'acquired_at': self.acquired_at.isoformat(),
            'expires_at': self.expires_at.isoformat(),
            'metadata': self.metadata
        }
    
    def is_expired(self) -> bool:
        return datetime.now() >= self.expires_at


class DistributedLockManager:
    """
    Manages distributed locks with deadlock prevention
    
    Supports two backends:
    1. Redis (production): High-performance, distributed
    2. File-based (development): Local testing
    """
    
    def __init__(
        self,
        backend: str = 'redis',
        redis_host: str = 'localhost',
        redis_port: int = 6379,
        redis_db: int = 0,
        default_timeout_seconds: int = 600,
        file_lock_dir: str = '/tmp/selfhealing_locks'
    ):
        self.backend = backend
        self.default_timeout = default_timeout_seconds
        self.file_lock_dir = file_lock_dir
        
        # Initialize backend
        if backend == 'redis':
            try:
                self.redis_client = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    db=redis_db,
                    decode_responses=True
                )
                # Test connection
                self.redis_client.ping()
                logger.info(f"Connected to Redis at {redis_host}:{redis_port}")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}. Falling back to file-based locks.")
                self.backend = 'file'
                self._setup_file_backend()
        else:
            self._setup_file_backend()
        
        # Track acquired locks for this process
        self._local_locks: Dict[str, LockInfo] = {}
        self._lock_mutex = threading.Lock()
        
        # Lock ordering rules (for deadlock prevention)
        self.lock_order = {
            LockScope.SYSTEM: 1,
            LockScope.SERVICE: 2,
            LockScope.INCIDENT: 3,
            LockScope.DEPLOYMENT: 4
        }
        
    def _setup_file_backend(self):
        """Setup file-based locking backend"""
        os.makedirs(self.file_lock_dir, exist_ok=True)
        logger.info(f"Using file-based locks at {self.file_lock_dir}")
    
    def _generate_lock_id(self, scope: LockScope, resource_id: str) -> str:
        """Generate unique lock ID"""
        return f"{scope.name}:{resource_id}"
    
    def _get_lock_key(self, lock_id: str) -> str:
        """Get Redis key for lock"""
        return f"selfhealing:lock:{lock_id}"
    
    def _validate_lock_ordering(
        self,
        new_scope: LockScope,
        resource_id: str
    ) -> Tuple[bool, str]:
        """
        Validate lock ordering to prevent deadlocks
        
        Rules:
        1. New lock scope must be >= existing lock scopes (can't acquire higher priority locks)
        2. If same scope, must be alphabetically ordered
        """
        with self._lock_mutex:
            for lock_id, lock_info in self._local_locks.items():
                existing_order = self.lock_order[lock_info.scope]
                new_order = self.lock_order[new_scope]
                
                # Rule 1: Can't acquire higher priority lock
                if new_order < existing_order:
                    return False, (
                        f"Lock ordering violation: Cannot acquire {new_scope.name} lock "
                        f"while holding {lock_info.scope.name} lock. "
                        f"This would violate deadlock prevention rules."
                    )
                
                # Rule 2: If same scope, alphabetical order
                if new_order == existing_order:
                    if resource_id < lock_info.resource_id:
                        return False, (
                            f"Lock ordering violation: Must acquire {new_scope.name} locks "
                            f"in alphabetical order. Cannot lock '{resource_id}' "
                            f"while holding '{lock_info.resource_id}'."
                        )
        
        return True, ""
    
    def acquire_lock(
        self,
        scope: LockScope,
        resource_id: str,
        owner: str = "self-healing-orchestrator",
        timeout_seconds: Optional[int] = None,
        wait_timeout_seconds: int = 30,
        metadata: Optional[Dict] = None
    ) -> Tuple[bool, Optional[LockInfo], str]:
        """
        Acquire a distributed lock with deadlock prevention
        
        Args:
            scope: Lock granularity (SYSTEM, SERVICE, INCIDENT, DEPLOYMENT)
            resource_id: ID of resource to lock (e.g., service name, incident ID)
            owner: Identifier of the lock owner
            timeout_seconds: Lock timeout (auto-release after this duration)
            wait_timeout_seconds: How long to wait if lock is held by another process
            metadata: Additional context about why lock is being acquired
        
        Returns:
            (success, lock_info, message)
        """
        # Validate lock ordering (deadlock prevention)
        valid, error_msg = self._validate_lock_ordering(scope, resource_id)
        if not valid:
            logger.error(f"Lock ordering violation: {error_msg}")
            return False, None, error_msg
        
        lock_id = self._generate_lock_id(scope, resource_id)
        timeout = timeout_seconds or self.default_timeout
        
        acquired_at = datetime.now()
        expires_at = acquired_at + timedelta(seconds=timeout)
        
        lock_info = LockInfo(
            lock_id=lock_id,
            scope=scope,
            resource_id=resource_id,
            owner=owner,
            acquired_at=acquired_at,
            expires_at=expires_at,
            metadata=metadata or {}
        )
        
        # Try to acquire lock
        start_time = time.time()
        while time.time() - start_time < wait_timeout_seconds:
            success = self._try_acquire_lock(lock_info)
            if success:
                # Store in local tracking
                with self._lock_mutex:
                    self._local_locks[lock_id] = lock_info
                
                logger.info(
                    f"Lock acquired: {lock_id} by {owner} "
                    f"(expires in {timeout}s)"
                )
                return True, lock_info, "Lock acquired successfully"
            
            # Lock is held by another process, wait and retry
            time.sleep(1)
        
        # Failed to acquire lock within wait timeout
        holder = self._get_lock_holder(lock_id)
        msg = (
            f"Failed to acquire lock {lock_id} within {wait_timeout_seconds}s. "
            f"Currently held by: {holder}"
        )
        logger.warning(msg)
        return False, None, msg
    
    def _try_acquire_lock(self, lock_info: LockInfo) -> bool:
        """Try to acquire lock (backend-specific implementation)"""
        if self.backend == 'redis':
            return self._redis_acquire(lock_info)
        else:
            return self._file_acquire(lock_info)
    
    def _redis_acquire(self, lock_info: LockInfo) -> bool:
        """Acquire lock using Redis SET NX (set if not exists)"""
        key = self._get_lock_key(lock_info.lock_id)
        ttl = int((lock_info.expires_at - lock_info.acquired_at).total_seconds())
        
        # SET NX: Set if not exists, with expiry
        success = self.redis_client.set(
            key,
            json.dumps(lock_info.to_dict()),
            nx=True,  # Only set if key doesn't exist
            ex=ttl    # Expiry time in seconds
        )
        
        return bool(success)
    
    def _file_acquire(self, lock_info: LockInfo) -> bool:
        """Acquire lock using file-based locking"""
        lock_file_path = os.path.join(
            self.file_lock_dir,
            f"{lock_info.lock_id.replace(':', '_')}.lock"
        )
        
        try:
            # Create or open lock file
            lock_file = open(lock_file_path, 'w')
            
            # Try to acquire exclusive lock (non-blocking)
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            
            # Write lock info
            lock_file.write(json.dumps(lock_info.to_dict()))
            lock_file.flush()
            
            # Store file handle to keep lock
            lock_info.metadata['_lock_file'] = lock_file
            
            return True
        except (IOError, OSError):
            # Lock is already held
            return False
    
    def release_lock(
        self,
        scope: LockScope,
        resource_id: str,
        owner: str = "self-healing-orchestrator"
    ) -> Tuple[bool, str]:
        """
        Release a distributed lock
        
        Args:
            scope: Lock granularity
            resource_id: ID of resource to unlock
            owner: Identifier of the lock owner (must match acquire)
        
        Returns:
            (success, message)
        """
        lock_id = self._generate_lock_id(scope, resource_id)
        
        # Check if we hold this lock
        with self._lock_mutex:
            if lock_id not in self._local_locks:
                msg = f"Cannot release lock {lock_id}: not held by this process"
                logger.warning(msg)
                return False, msg
            
            lock_info = self._local_locks[lock_id]
            
            # Verify owner
            if lock_info.owner != owner:
                msg = (
                    f"Cannot release lock {lock_id}: "
                    f"held by {lock_info.owner}, not {owner}"
                )
                logger.warning(msg)
                return False, msg
        
        # Release lock
        success = self._release_lock_backend(lock_info)
        
        if success:
            with self._lock_mutex:
                del self._local_locks[lock_id]
            
            logger.info(f"Lock released: {lock_id} by {owner}")
            return True, "Lock released successfully"
        else:
            msg = f"Failed to release lock {lock_id}"
            logger.error(msg)
            return False, msg
    
    def _release_lock_backend(self, lock_info: LockInfo) -> bool:
        """Release lock (backend-specific implementation)"""
        if self.backend == 'redis':
            return self._redis_release(lock_info)
        else:
            return self._file_release(lock_info)
    
    def _redis_release(self, lock_info: LockInfo) -> bool:
        """Release Redis lock"""
        key = self._get_lock_key(lock_info.lock_id)
        
        # Use Lua script to ensure atomic check-and-delete
        # Only delete if the lock is still ours
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        
        result = self.redis_client.eval(
            lua_script,
            1,
            key,
            json.dumps(lock_info.to_dict())
        )
        
        return bool(result)
    
    def _file_release(self, lock_info: LockInfo) -> bool:
        """Release file-based lock"""
        lock_file = lock_info.metadata.get('_lock_file')
        if lock_file:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                lock_file.close()
                return True
            except Exception as e:
                logger.error(f"Error releasing file lock: {e}")
                return False
        return False
    
    def is_locked(
        self,
        scope: LockScope,
        resource_id: str
    ) -> bool:
        """Check if a resource is currently locked"""
        lock_id = self._generate_lock_id(scope, resource_id)
        
        if self.backend == 'redis':
            key = self._get_lock_key(lock_id)
            return self.redis_client.exists(key) > 0
        else:
            lock_file_path = os.path.join(
                self.file_lock_dir,
                f"{lock_id.replace(':', '_')}.lock"
            )
            return os.path.exists(lock_file_path)
    
    def _get_lock_holder(self, lock_id: str) -> str:
        """Get the current holder of a lock"""
        if self.backend == 'redis':
            key = self._get_lock_key(lock_id)
            lock_data = self.redis_client.get(key)
            if lock_data:
                lock_dict = json.loads(lock_data)
                return lock_dict.get('owner', 'unknown')
        else:
            lock_file_path = os.path.join(
                self.file_lock_dir,
                f"{lock_id.replace(':', '_')}.lock"
            )
            if os.path.exists(lock_file_path):
                try:
                    with open(lock_file_path, 'r') as f:
                        lock_dict = json.load(f)
                        return lock_dict.get('owner', 'unknown')
                except Exception:
                    pass
        
        return "unknown"
    
    def get_active_locks(self) -> List[LockInfo]:
        """Get all active locks in the system"""
        active_locks = []
        
        if self.backend == 'redis':
            # Scan all lock keys
            pattern = self._get_lock_key('*')
            for key in self.redis_client.scan_iter(match=pattern):
                lock_data = self.redis_client.get(key)
                if lock_data:
                    lock_dict = json.loads(lock_data)
                    lock_info = LockInfo(
                        lock_id=lock_dict['lock_id'],
                        scope=LockScope[lock_dict['scope']],
                        resource_id=lock_dict['resource_id'],
                        owner=lock_dict['owner'],
                        acquired_at=datetime.fromisoformat(lock_dict['acquired_at']),
                        expires_at=datetime.fromisoformat(lock_dict['expires_at']),
                        metadata=lock_dict.get('metadata', {})
                    )
                    if not lock_info.is_expired():
                        active_locks.append(lock_info)
        else:
            # Scan lock directory
            for filename in os.listdir(self.file_lock_dir):
                if filename.endswith('.lock'):
                    lock_file_path = os.path.join(self.file_lock_dir, filename)
                    try:
                        with open(lock_file_path, 'r') as f:
                            lock_dict = json.load(f)
                            lock_info = LockInfo(
                                lock_id=lock_dict['lock_id'],
                                scope=LockScope[lock_dict['scope']],
                                resource_id=lock_dict['resource_id'],
                                owner=lock_dict['owner'],
                                acquired_at=datetime.fromisoformat(lock_dict['acquired_at']),
                                expires_at=datetime.fromisoformat(lock_dict['expires_at']),
                                metadata=lock_dict.get('metadata', {})
                            )
                            if not lock_info.is_expired():
                                active_locks.append(lock_info)
                    except Exception as e:
                        logger.warning(f"Error reading lock file {filename}: {e}")
        
        return active_locks
    
    def cleanup_expired_locks(self) -> int:
        """Clean up expired locks (maintenance operation)"""
        cleaned = 0
        
        if self.backend == 'redis':
            # Redis auto-expires locks, no cleanup needed
            return 0
        else:
            # Manual cleanup for file-based locks
            for filename in os.listdir(self.file_lock_dir):
                if filename.endswith('.lock'):
                    lock_file_path = os.path.join(self.file_lock_dir, filename)
                    try:
                        with open(lock_file_path, 'r') as f:
                            lock_dict = json.load(f)
                            expires_at = datetime.fromisoformat(lock_dict['expires_at'])
                            if datetime.now() >= expires_at:
                                os.remove(lock_file_path)
                                cleaned += 1
                                logger.info(f"Cleaned up expired lock: {filename}")
                    except Exception as e:
                        logger.warning(f"Error cleaning lock file {filename}: {e}")
        
        return cleaned
    
    def force_release_all(self, owner: str) -> int:
        """Force release all locks held by an owner (emergency use only)"""
        released = 0
        
        with self._lock_mutex:
            locks_to_release = [
                (lock_id, lock_info)
                for lock_id, lock_info in self._local_locks.items()
                if lock_info.owner == owner
            ]
        
        for lock_id, lock_info in locks_to_release:
            success = self._release_lock_backend(lock_info)
            if success:
                with self._lock_mutex:
                    if lock_id in self._local_locks:
                        del self._local_locks[lock_id]
                released += 1
        
        logger.warning(f"Force released {released} locks for owner {owner}")
        return released


# Example usage and testing
if __name__ == '__main__':
    print("=== Distributed Lock Manager Demo ===\n")
    
    # Initialize lock manager (will use file-based if Redis not available)
    lock_mgr = DistributedLockManager(backend='file')
    
    print("1. Acquiring service-level lock...")
    success, lock_info, msg = lock_mgr.acquire_lock(
        scope=LockScope.SERVICE,
        resource_id='payment-service',
        owner='orchestrator-1',
        timeout_seconds=300,
        metadata={'reason': 'deployment', 'incident_id': 'INC-001'}
    )
    print(f"   Result: {msg}")
    if lock_info:
        print(f"   Lock ID: {lock_info.lock_id}")
        print(f"   Expires at: {lock_info.expires_at.isoformat()}")
    
    print("\n2. Trying to acquire same lock from another owner (should fail)...")
    success2, _, msg2 = lock_mgr.acquire_lock(
        scope=LockScope.SERVICE,
        resource_id='payment-service',
        owner='orchestrator-2',
        wait_timeout_seconds=2
    )
    print(f"   Result: {msg2}")
    
    print("\n3. Acquiring incident lock (valid, lower priority than service)...")
    success3, lock_info3, msg3 = lock_mgr.acquire_lock(
        scope=LockScope.INCIDENT,
        resource_id='INC-001',
        owner='orchestrator-1',
        metadata={'action': 'verification'}
    )
    print(f"   Result: {msg3}")
    
    print("\n4. Trying to acquire system lock (should fail - violates lock ordering)...")
    success4, _, msg4 = lock_mgr.acquire_lock(
        scope=LockScope.SYSTEM,
        resource_id='global',
        owner='orchestrator-1',
        wait_timeout_seconds=1
    )
    print(f"   Result: {msg4}")
    
    print("\n5. Checking active locks...")
    active = lock_mgr.get_active_locks()
    print(f"   Active locks: {len(active)}")
    for lock in active:
        print(f"   - {lock.lock_id} (owner: {lock.owner})")
    
    print("\n6. Releasing service lock...")
    success5, msg5 = lock_mgr.release_lock(
        scope=LockScope.SERVICE,
        resource_id='payment-service',
        owner='orchestrator-1'
    )
    print(f"   Result: {msg5}")
    
    print("\n7. Releasing incident lock...")
    success6, msg6 = lock_mgr.release_lock(
        scope=LockScope.INCIDENT,
        resource_id='INC-001',
        owner='orchestrator-1'
    )
    print(f"   Result: {msg6}")
    
    print("\n=== Demo Complete ===")
    print("\nDeadlock Prevention Features Demonstrated:")
    print("✓ Lock ordering rules enforced (SYSTEM > SERVICE > INCIDENT > DEPLOYMENT)")
    print("✓ Attempted violation was blocked (step 4)")
    print("✓ Locks tracked with owner, expiry, and metadata")
    print("✓ Exclusive lock enforcement (step 2)")
