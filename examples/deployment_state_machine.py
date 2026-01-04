#!/usr/bin/env python3
"""
Deployment State Machine for Step 8: Deployment Automation

Models deployment as a state machine with explicit state transitions.
Ensures audit trail and safety controls for concurrency (Step 10 integration).

States: INIT → DEPLOYING → CANARY → PROMOTED → VERIFIED
                           ↓
                       ROLLBACK
"""

import json
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path


class DeploymentState(Enum):
    """Deployment state enumeration"""
    INIT = "init"
    BUILDING = "building"
    DEPLOYING = "deploying"
    CANARY = "canary"
    CANARY_WAITING = "canary_waiting"
    CANARY_EVALUATING = "canary_evaluating"
    PROMOTING = "promoting"
    PROMOTED = "promoted"
    VERIFYING = "verifying"
    VERIFIED = "verified"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


@dataclass
class StateTransition:
    """Record of a state transition"""
    from_state: DeploymentState
    to_state: DeploymentState
    timestamp: datetime
    reason: str
    metadata: Dict
    
    def to_dict(self) -> Dict:
        return {
            'from_state': self.from_state.value,
            'to_state': self.to_state.value,
            'timestamp': self.timestamp.isoformat(),
            'reason': self.reason,
            'metadata': self.metadata
        }


@dataclass
class DeploymentContext:
    """Context for a deployment"""
    deployment_id: str
    incident_id: str
    service_name: str
    image_tag: str
    commit_hash: str
    safety_artifact_path: Optional[str] = None
    canary_percentage: int = 0
    metadata: Dict = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


class DeploymentStateMachine:
    """Manages deployment state transitions with audit trail"""
    
    # Valid state transitions
    VALID_TRANSITIONS = {
        DeploymentState.INIT: [DeploymentState.BUILDING, DeploymentState.FAILED],
        DeploymentState.BUILDING: [DeploymentState.DEPLOYING, DeploymentState.FAILED],
        DeploymentState.DEPLOYING: [DeploymentState.CANARY, DeploymentState.PROMOTED, DeploymentState.FAILED],
        DeploymentState.CANARY: [DeploymentState.CANARY_WAITING, DeploymentState.ROLLING_BACK, DeploymentState.FAILED],
        DeploymentState.CANARY_WAITING: [DeploymentState.CANARY_EVALUATING, DeploymentState.ROLLING_BACK],
        DeploymentState.CANARY_EVALUATING: [DeploymentState.CANARY, DeploymentState.PROMOTING, DeploymentState.ROLLING_BACK, DeploymentState.FAILED],
        DeploymentState.PROMOTING: [DeploymentState.PROMOTED, DeploymentState.ROLLING_BACK, DeploymentState.FAILED],
        DeploymentState.PROMOTED: [DeploymentState.VERIFYING, DeploymentState.ROLLING_BACK],
        DeploymentState.VERIFYING: [DeploymentState.VERIFIED, DeploymentState.ROLLING_BACK],
        DeploymentState.VERIFIED: [],  # Terminal success state
        DeploymentState.ROLLING_BACK: [DeploymentState.ROLLED_BACK, DeploymentState.FAILED],
        DeploymentState.ROLLED_BACK: [],  # Terminal rollback state
        DeploymentState.FAILED: []  # Terminal failure state
    }
    
    def __init__(self, context: DeploymentContext, audit_dir: str = ".deployments"):
        self.context = context
        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        
        self.current_state = DeploymentState.INIT
        self.transitions: List[StateTransition] = []
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None
        
        # Initialize state file
        self._save_state()
    
    def transition(self, to_state: DeploymentState, reason: str, metadata: Optional[Dict] = None) -> bool:
        """
        Transition to a new state
        
        Args:
            to_state: Target state
            reason: Reason for transition
            metadata: Additional metadata
        
        Returns:
            True if transition successful, False otherwise
        """
        
        # Validate transition
        if not self._is_valid_transition(to_state):
            print(f"✗ Invalid transition: {self.current_state.value} → {to_state.value}")
            return False
        
        # Record transition
        transition = StateTransition(
            from_state=self.current_state,
            to_state=to_state,
            timestamp=datetime.now(),
            reason=reason,
            metadata=metadata or {}
        )
        
        self.transitions.append(transition)
        
        print(f"📍 {self.current_state.value} → {to_state.value}: {reason}")
        
        # Update state
        self.current_state = to_state
        
        # Check if terminal state
        if self._is_terminal_state(to_state):
            self.end_time = datetime.now()
        
        # Save state to disk
        self._save_state()
        
        return True
    
    def _is_valid_transition(self, to_state: DeploymentState) -> bool:
        """Check if transition is valid"""
        valid_next_states = self.VALID_TRANSITIONS.get(self.current_state, [])
        return to_state in valid_next_states
    
    def _is_terminal_state(self, state: DeploymentState) -> bool:
        """Check if state is terminal (no further transitions)"""
        return state in [
            DeploymentState.VERIFIED,
            DeploymentState.ROLLED_BACK,
            DeploymentState.FAILED
        ]
    
    def is_complete(self) -> bool:
        """Check if deployment is complete (success or failure)"""
        return self._is_terminal_state(self.current_state)
    
    def is_successful(self) -> bool:
        """Check if deployment was successful"""
        return self.current_state == DeploymentState.VERIFIED
    
    def is_rolled_back(self) -> bool:
        """Check if deployment was rolled back"""
        return self.current_state == DeploymentState.ROLLED_BACK
    
    def is_failed(self) -> bool:
        """Check if deployment failed"""
        return self.current_state == DeploymentState.FAILED
    
    def get_state_history(self) -> List[Dict]:
        """Get history of all state transitions"""
        return [t.to_dict() for t in self.transitions]
    
    def get_duration(self) -> float:
        """Get deployment duration in seconds"""
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()
    
    def _save_state(self):
        """Save current state to disk for audit"""
        
        state_data = {
            'deployment_id': self.context.deployment_id,
            'incident_id': self.context.incident_id,
            'service_name': self.context.service_name,
            'image_tag': self.context.image_tag,
            'commit_hash': self.context.commit_hash,
            'current_state': self.current_state.value,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_seconds': self.get_duration(),
            'transitions': self.get_state_history(),
            'context': self.context.to_dict()
        }
        
        state_file = self.audit_dir / f"deployment_{self.context.deployment_id}.json"
        
        with open(state_file, 'w') as f:
            json.dump(state_data, f, indent=2)
    
    def generate_state_diagram(self) -> str:
        """Generate ASCII state diagram"""
        
        diagram = "\n" + "="*80 + "\n"
        diagram += "DEPLOYMENT STATE MACHINE\n"
        diagram += "="*80 + "\n\n"
        diagram += f"Deployment ID: {self.context.deployment_id}\n"
        diagram += f"Service: {self.context.service_name}\n"
        diagram += f"Image: {self.context.image_tag}\n"
        diagram += f"Current State: {self.current_state.value}\n"
        diagram += f"Duration: {self.get_duration():.1f}s\n\n"
        diagram += "State Transitions:\n"
        diagram += "-"*80 + "\n"
        
        for i, transition in enumerate(self.transitions, 1):
            elapsed = (transition.timestamp - self.start_time).total_seconds()
            diagram += f"{i}. [{elapsed:6.1f}s] {transition.from_state.value:20} → {transition.to_state.value:20}\n"
            diagram += f"   Reason: {transition.reason}\n"
            if transition.metadata:
                diagram += f"   Metadata: {json.dumps(transition.metadata, indent=6)}\n"
        
        diagram += "="*80 + "\n"
        
        return diagram
    
    @classmethod
    def load_from_file(cls, deployment_id: str, audit_dir: str = ".deployments") -> 'DeploymentStateMachine':
        """Load deployment state from disk"""
        
        state_file = Path(audit_dir) / f"deployment_{deployment_id}.json"
        
        if not state_file.exists():
            raise FileNotFoundError(f"Deployment state not found: {deployment_id}")
        
        with open(state_file, 'r') as f:
            state_data = json.load(f)
        
        # Reconstruct context
        context_data = state_data['context']
        context = DeploymentContext(**context_data)
        
        # Create state machine
        sm = cls(context, audit_dir)
        
        # Restore state
        sm.current_state = DeploymentState(state_data['current_state'])
        sm.start_time = datetime.fromisoformat(state_data['start_time'])
        if state_data['end_time']:
            sm.end_time = datetime.fromisoformat(state_data['end_time'])
        
        # Restore transitions
        sm.transitions = []
        for t_data in state_data['transitions']:
            transition = StateTransition(
                from_state=DeploymentState(t_data['from_state']),
                to_state=DeploymentState(t_data['to_state']),
                timestamp=datetime.fromisoformat(t_data['timestamp']),
                reason=t_data['reason'],
                metadata=t_data['metadata']
            )
            sm.transitions.append(transition)
        
        return sm


# Example usage
if __name__ == "__main__":
    # Create deployment context
    context = DeploymentContext(
        deployment_id="DEP-001",
        incident_id="INC-001",
        service_name="payment-service",
        image_tag="v2.1.0-abc123",
        commit_hash="abc123def456",
        safety_artifact_path="/artifacts/safety_report_INC-001.json"
    )
    
    # Initialize state machine
    sm = DeploymentStateMachine(context)
    
    # Simulate deployment flow
    sm.transition(DeploymentState.BUILDING, "Building Docker image")
    time.sleep(1)
    
    sm.transition(DeploymentState.DEPLOYING, "Deploying to Kubernetes")
    time.sleep(1)
    
    sm.transition(DeploymentState.CANARY, "Starting canary rollout", {'canary_percentage': 5})
    time.sleep(1)
    
    sm.transition(DeploymentState.CANARY_WAITING, "Waiting for metrics to stabilize")
    time.sleep(2)
    
    sm.transition(DeploymentState.CANARY_EVALUATING, "Evaluating health gates")
    time.sleep(1)
    
    # Health gates pass, continue canary
    sm.transition(DeploymentState.CANARY, "Increasing canary traffic", {'canary_percentage': 25})
    time.sleep(1)
    
    sm.transition(DeploymentState.CANARY_WAITING, "Waiting for metrics")
    time.sleep(2)
    
    sm.transition(DeploymentState.CANARY_EVALUATING, "Evaluating health gates")
    time.sleep(1)
    
    # All gates pass, promote
    sm.transition(DeploymentState.PROMOTING, "Promoting to 100%")
    time.sleep(1)
    
    sm.transition(DeploymentState.PROMOTED, "Deployment promoted")
    time.sleep(1)
    
    sm.transition(DeploymentState.VERIFYING, "Verifying deployment success")
    time.sleep(1)
    
    sm.transition(DeploymentState.VERIFIED, "Deployment verified and complete")
    
    # Print state diagram
    print(sm.generate_state_diagram())
    
    print(f"\nDeployment complete: {sm.is_successful()}")
    print(f"Total duration: {sm.get_duration():.1f}s")
