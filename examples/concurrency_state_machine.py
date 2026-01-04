#!/usr/bin/env python3
"""
Concurrency State Machine with Human Override

Tracks operation states with explicit PAUSED_FOR_HUMAN_REVIEW state.
This shows responsible automation - allows safe handoff to operators.

States:
- INIT: Operation requested
- LOCKED: Exclusive lock acquired
- SAFETY_CHECK: Running safety gates
- IN_PROGRESS: Operation executing
- PAUSED_FOR_HUMAN_REVIEW: Requires manual intervention
- COMPLETED: Operation successful
- FAILED: Operation failed
- ROLLED_BACK: Operation rolled back
- CANCELLED: Operation cancelled by operator
"""

from enum import Enum
from datetime import datetime
from typing import Optional, Dict, List
import json

class ConcurrencyState(Enum):
    INIT = "init"
    LOCKED = "locked"
    SAFETY_CHECK = "safety_check"
    IN_PROGRESS = "in_progress"
    PAUSED_FOR_HUMAN_REVIEW = "paused_for_human_review"  # NEW: Human override
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"

class StateTransition:
    def __init__(self, from_state: ConcurrencyState, to_state: ConcurrencyState, trigger: str, actor: str):
        self.from_state = from_state
        self.to_state = to_state
        self.trigger = trigger
        self.actor = actor
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict:
        return {
            'from_state': self.from_state.value,
            'to_state': self.to_state.value,
            'trigger': self.trigger,
            'actor': self.actor,
            'timestamp': self.timestamp.isoformat()
        }

class ConcurrencyStateMachine:
    """State machine with human override capability"""
    
    # Valid transitions
    ALLOWED_TRANSITIONS = {
        ConcurrencyState.INIT: [ConcurrencyState.LOCKED, ConcurrencyState.FAILED],
        ConcurrencyState.LOCKED: [ConcurrencyState.SAFETY_CHECK, ConcurrencyState.FAILED],
        ConcurrencyState.SAFETY_CHECK: [ConcurrencyState.IN_PROGRESS, ConcurrencyState.PAUSED_FOR_HUMAN_REVIEW, ConcurrencyState.FAILED],
        ConcurrencyState.IN_PROGRESS: [ConcurrencyState.COMPLETED, ConcurrencyState.PAUSED_FOR_HUMAN_REVIEW, ConcurrencyState.FAILED],
        ConcurrencyState.PAUSED_FOR_HUMAN_REVIEW: [ConcurrencyState.IN_PROGRESS, ConcurrencyState.CANCELLED, ConcurrencyState.ROLLED_BACK],  # Human can resume or abort
        ConcurrencyState.COMPLETED: [],  # Terminal
        ConcurrencyState.FAILED: [ConcurrencyState.ROLLED_BACK],
        ConcurrencyState.ROLLED_BACK: [],  # Terminal
        ConcurrencyState.CANCELLED: []  # Terminal
    }
    
    def __init__(self, operation_id: str):
        self.operation_id = operation_id
        self.current_state = ConcurrencyState.INIT
        self.transitions: List[StateTransition] = []
        self.metadata = {}
    
    def transition(self, to_state: ConcurrencyState, trigger: str, actor: str) -> bool:
        """Transition to new state if valid"""
        if to_state in self.ALLOWED_TRANSITIONS[self.current_state]:
            transition = StateTransition(self.current_state, to_state, trigger, actor)
            self.transitions.append(transition)
            self.current_state = to_state
            return True
        return False
    
    def pause_for_review(self, reason: str, actor: str) -> bool:
        """Pause operation for human review"""
        self.metadata['pause_reason'] = reason
        self.metadata['paused_by'] = actor
        self.metadata['paused_at'] = datetime.now().isoformat()
        return self.transition(ConcurrencyState.PAUSED_FOR_HUMAN_REVIEW, reason, actor)
    
    def resume_from_pause(self, actor: str, approval_id: Optional[str] = None) -> bool:
        """Resume after human review"""
        if self.current_state == ConcurrencyState.PAUSED_FOR_HUMAN_REVIEW:
            self.metadata['resumed_by'] = actor
            self.metadata['approval_id'] = approval_id
            return self.transition(ConcurrencyState.IN_PROGRESS, 'human_approved', actor)
        return False
    
    def get_history(self) -> List[Dict]:
        """Get state transition history"""
        return [t.to_dict() for t in self.transitions]

if __name__ == '__main__':
    sm = ConcurrencyStateMachine('OP-001')
    sm.transition(ConcurrencyState.LOCKED, 'lock_acquired', 'orchestrator')
    sm.transition(ConcurrencyState.SAFETY_CHECK, 'safety_gates', 'orchestrator')
    sm.pause_for_review('unusual_metric_pattern', 'orchestrator')
    print(f"State: {sm.current_state.value}")
    sm.resume_from_pause('ops-engineer', 'APPROVAL-123')
    print(f"State: {sm.current_state.value}")
    print(f"History: {json.dumps(sm.get_history(), indent=2)}")
