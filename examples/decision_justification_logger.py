#!/usr/bin/env python3
"""
Decision Justification Logger
==============================

Captures the reasoning behind every automated decision in the self-healing system.
This provides explainability and auditability for autonomous actions.

Purpose:
    - Log WHY each decision was made (not just WHAT)
    - Provide human-readable explanations for automation
    - Enable audit trails for compliance
    - Support debugging when automation goes wrong

Usage:
    from decision_justification_logger import DecisionLogger, DecisionContext
    
    logger = DecisionLogger()
    
    with logger.decision_context("deployment", "deploy-12345") as ctx:
        ctx.add_input("error_rate", 15.2, "Current error rate exceeds threshold")
        ctx.add_factor("risk_score", 0.18, "Low risk - localized change")
        ctx.add_constraint("business_hours", True, "Change allowed during business hours")
        
        # Make decision
        decision = "proceed_with_deployment"
        
        ctx.record_decision(
            decision=decision,
            reasoning="Error rate critical (15.2% > 5%), risk acceptable (0.18), no blocking constraints",
            alternatives_considered=["rollback", "manual_review", "proceed"],
            confidence=0.92
        )
"""

import json
import time
import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from dataclasses import dataclass, field, asdict
from enum import Enum
from contextlib import contextmanager
import threading


logger = logging.getLogger(__name__)


class DecisionType(Enum):
    """Types of decisions tracked."""
    INCIDENT_DETECTION = "incident_detection"
    RCA_ANALYSIS = "rca_analysis"
    FIX_GENERATION = "fix_generation"
    SAFETY_GATE = "safety_gate"
    DEPLOYMENT = "deployment"
    ROLLBACK = "rollback"
    VERIFICATION = "verification"
    CONCURRENCY = "concurrency"
    HUMAN_ESCALATION = "human_escalation"


class ConfidenceLevel(Enum):
    """Confidence levels for decisions."""
    VERY_HIGH = "very_high"  # >90%
    HIGH = "high"            # 80-90%
    MEDIUM = "medium"        # 60-80%
    LOW = "low"              # 40-60%
    VERY_LOW = "very_low"    # <40%
    
    @staticmethod
    def from_score(score: float) -> 'ConfidenceLevel':
        """Convert numeric score to confidence level."""
        if score >= 0.9:
            return ConfidenceLevel.VERY_HIGH
        elif score >= 0.8:
            return ConfidenceLevel.HIGH
        elif score >= 0.6:
            return ConfidenceLevel.MEDIUM
        elif score >= 0.4:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW


@dataclass
class DecisionInput:
    """Represents an input to a decision."""
    name: str
    value: Any
    explanation: str
    source: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": str(self.value),
            "explanation": self.explanation,
            "source": self.source,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class DecisionFactor:
    """Represents a factor influencing the decision."""
    name: str
    value: Any
    weight: float  # 0.0 to 1.0
    explanation: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": str(self.value),
            "weight": self.weight,
            "explanation": self.explanation
        }


@dataclass
class DecisionConstraint:
    """Represents a constraint on the decision."""
    name: str
    satisfied: bool
    explanation: str
    blocking: bool = False  # If True, constraint blocks decision if not satisfied
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "satisfied": self.satisfied,
            "explanation": self.explanation,
            "blocking": self.blocking,
            "status": "✓" if self.satisfied else ("🚫" if self.blocking else "⚠️")
        }


@dataclass
class AlternativeOption:
    """Represents an alternative decision option considered."""
    option: str
    score: float
    pros: List[str]
    cons: List[str]
    rejected_reason: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "option": self.option,
            "score": self.score,
            "pros": self.pros,
            "cons": self.cons,
            "rejected_reason": self.rejected_reason
        }


@dataclass
class DecisionRecord:
    """Complete record of a decision."""
    decision_id: str
    decision_type: DecisionType
    timestamp: datetime
    
    # Context
    incident_id: Optional[str] = None
    service_name: Optional[str] = None
    
    # Inputs
    inputs: List[DecisionInput] = field(default_factory=list)
    factors: List[DecisionFactor] = field(default_factory=list)
    constraints: List[DecisionConstraint] = field(default_factory=list)
    
    # Decision
    decision: Optional[str] = None
    reasoning: Optional[str] = None
    confidence: Optional[float] = None
    confidence_level: Optional[ConfidenceLevel] = None
    
    # Alternatives
    alternatives: List[AlternativeOption] = field(default_factory=list)
    
    # Outcome (filled in later)
    outcome: Optional[str] = None
    outcome_timestamp: Optional[datetime] = None
    was_correct: Optional[bool] = None
    
    # Metadata
    duration_ms: Optional[float] = None
    decision_maker: str = "autonomous_system"
    human_override: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "decision_id": self.decision_id,
            "decision_type": self.decision_type.value,
            "timestamp": self.timestamp.isoformat(),
            "incident_id": self.incident_id,
            "service_name": self.service_name,
            "inputs": [inp.to_dict() for inp in self.inputs],
            "factors": [f.to_dict() for f in self.factors],
            "constraints": [c.to_dict() for c in self.constraints],
            "decision": self.decision,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "confidence_level": self.confidence_level.value if self.confidence_level else None,
            "alternatives": [alt.to_dict() for alt in self.alternatives],
            "outcome": self.outcome,
            "outcome_timestamp": self.outcome_timestamp.isoformat() if self.outcome_timestamp else None,
            "was_correct": self.was_correct,
            "duration_ms": self.duration_ms,
            "decision_maker": self.decision_maker,
            "human_override": self.human_override
        }
    
    def to_human_readable(self) -> str:
        """Generate human-readable explanation."""
        lines = []
        lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"Decision: {self.decision_type.value.upper()}")
        lines.append(f"ID: {self.decision_id}")
        lines.append(f"Time: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        if self.incident_id:
            lines.append(f"\n📋 Context:")
            lines.append(f"   Incident: {self.incident_id}")
            if self.service_name:
                lines.append(f"   Service: {self.service_name}")
        
        if self.inputs:
            lines.append(f"\n📊 Inputs:")
            for inp in self.inputs:
                lines.append(f"   • {inp.name}: {inp.value}")
                lines.append(f"     → {inp.explanation}")
        
        if self.factors:
            lines.append(f"\n⚖️  Decision Factors:")
            for factor in sorted(self.factors, key=lambda f: f.weight, reverse=True):
                weight_str = "█" * int(factor.weight * 10)
                lines.append(f"   • {factor.name}: {factor.value} (weight: {factor.weight:.2f})")
                lines.append(f"     {weight_str}")
                lines.append(f"     → {factor.explanation}")
        
        if self.constraints:
            lines.append(f"\n🔒 Constraints:")
            for constraint in self.constraints:
                status = "✓" if constraint.satisfied else ("🚫" if constraint.blocking else "⚠️")
                blocking = " [BLOCKING]" if constraint.blocking else ""
                lines.append(f"   {status} {constraint.name}{blocking}")
                lines.append(f"     → {constraint.explanation}")
        
        if self.decision:
            lines.append(f"\n🎯 Decision Made: {self.decision}")
            if self.reasoning:
                lines.append(f"\n💭 Reasoning:")
                for line in self.reasoning.split('\n'):
                    lines.append(f"   {line}")
            
            if self.confidence is not None:
                conf_level = self.confidence_level.value if self.confidence_level else "unknown"
                lines.append(f"\n📈 Confidence: {self.confidence*100:.1f}% ({conf_level})")
        
        if self.alternatives:
            lines.append(f"\n🔀 Alternatives Considered:")
            for alt in sorted(self.alternatives, key=lambda a: a.score, reverse=True):
                chosen = "✓ CHOSEN" if alt.option == self.decision else "✗ REJECTED"
                lines.append(f"   {chosen}: {alt.option} (score: {alt.score:.2f})")
                if alt.pros:
                    lines.append(f"      Pros: {', '.join(alt.pros)}")
                if alt.cons:
                    lines.append(f"      Cons: {', '.join(alt.cons)}")
                if alt.rejected_reason:
                    lines.append(f"      → Rejected: {alt.rejected_reason}")
        
        if self.outcome:
            lines.append(f"\n📊 Outcome:")
            lines.append(f"   Status: {self.outcome}")
            if self.was_correct is not None:
                correctness = "✓ CORRECT" if self.was_correct else "✗ INCORRECT"
                lines.append(f"   Decision Quality: {correctness}")
        
        if self.duration_ms:
            lines.append(f"\n⏱️  Decision Time: {self.duration_ms:.2f}ms")
        
        if self.human_override:
            lines.append(f"\n👤 Note: Human override applied")
        
        lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
        
        return "\n".join(lines)


class DecisionContext:
    """Context manager for building decision records."""
    
    def __init__(self, decision_id: str, decision_type: DecisionType, logger: 'DecisionLogger'):
        self.decision_id = decision_id
        self.decision_type = decision_type
        self.logger = logger
        self.record = DecisionRecord(
            decision_id=decision_id,
            decision_type=decision_type,
            timestamp=datetime.now()
        )
        self.start_time = time.time()
    
    def set_context(self, incident_id: Optional[str] = None, service_name: Optional[str] = None):
        """Set incident context."""
        if incident_id:
            self.record.incident_id = incident_id
        if service_name:
            self.record.service_name = service_name
    
    def add_input(self, name: str, value: Any, explanation: str, source: Optional[str] = None):
        """Add an input to the decision."""
        self.record.inputs.append(
            DecisionInput(name=name, value=value, explanation=explanation, source=source)
        )
    
    def add_factor(self, name: str, value: Any, weight: float, explanation: str):
        """Add a decision factor."""
        self.record.factors.append(
            DecisionFactor(name=name, value=value, weight=weight, explanation=explanation)
        )
    
    def add_constraint(self, name: str, satisfied: bool, explanation: str, blocking: bool = False):
        """Add a constraint."""
        self.record.constraints.append(
            DecisionConstraint(name=name, satisfied=satisfied, explanation=explanation, blocking=blocking)
        )
    
    def add_alternative(self, option: str, score: float, pros: List[str], cons: List[str], 
                       rejected_reason: Optional[str] = None):
        """Add an alternative option."""
        self.record.alternatives.append(
            AlternativeOption(option=option, score=score, pros=pros, cons=cons, 
                            rejected_reason=rejected_reason)
        )
    
    def record_decision(self, decision: str, reasoning: str, confidence: float,
                       alternatives_considered: Optional[List[str]] = None):
        """Record the final decision."""
        self.record.decision = decision
        self.record.reasoning = reasoning
        self.record.confidence = confidence
        self.record.confidence_level = ConfidenceLevel.from_score(confidence)
        
        # Calculate duration
        self.record.duration_ms = (time.time() - self.start_time) * 1000
    
    def set_outcome(self, outcome: str, was_correct: bool):
        """Set the outcome of the decision (called later)."""
        self.record.outcome = outcome
        self.record.outcome_timestamp = datetime.now()
        self.record.was_correct = was_correct
    
    def human_override(self, by_user: str, reason: str):
        """Mark that a human overrode this decision."""
        self.record.human_override = True
        self.record.decision_maker = f"human:{by_user}"
        self.record.reasoning += f"\n\n[HUMAN OVERRIDE by {by_user}]: {reason}"
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Save the decision record
        self.logger.save_decision(self.record)
        return False


class DecisionLogger:
    """Main decision logger."""
    
    def __init__(self, log_file: str = "/tmp/decision_justifications.jsonl"):
        self.log_file = log_file
        self.decisions: List[DecisionRecord] = []
        self._lock = threading.Lock()
        
    @contextmanager
    def decision_context(self, decision_type: Union[str, DecisionType], 
                        decision_id: Optional[str] = None) -> DecisionContext:
        """Create a decision context."""
        if isinstance(decision_type, str):
            decision_type = DecisionType(decision_type)
        
        if decision_id is None:
            decision_id = f"{decision_type.value}-{int(time.time() * 1000)}"
        
        ctx = DecisionContext(decision_id, decision_type, self)
        yield ctx
    
    def save_decision(self, record: DecisionRecord):
        """Save a decision record."""
        with self._lock:
            self.decisions.append(record)
            
            # Append to JSONL file
            try:
                with open(self.log_file, 'a') as f:
                    f.write(json.dumps(record.to_dict()) + '\n')
            except Exception as e:
                logger.error(f"Failed to write decision log: {e}")
    
    def get_decisions(self, decision_type: Optional[DecisionType] = None,
                     incident_id: Optional[str] = None) -> List[DecisionRecord]:
        """Retrieve decisions with optional filtering."""
        with self._lock:
            results = self.decisions.copy()
        
        if decision_type:
            results = [d for d in results if d.decision_type == decision_type]
        
        if incident_id:
            results = [d for d in results if d.incident_id == incident_id]
        
        return results
    
    def print_decision(self, decision_id: str):
        """Print a human-readable decision."""
        with self._lock:
            for record in self.decisions:
                if record.decision_id == decision_id:
                    print(record.to_human_readable())
                    return
        
        print(f"Decision {decision_id} not found")
    
    def generate_report(self, incident_id: str) -> str:
        """Generate a complete decision report for an incident."""
        decisions = self.get_decisions(incident_id=incident_id)
        
        if not decisions:
            return f"No decisions found for incident {incident_id}"
        
        lines = []
        lines.append(f"╔══════════════════════════════════════════════════════════════════════╗")
        lines.append(f"║  DECISION JUSTIFICATION REPORT                                       ║")
        lines.append(f"║  Incident: {incident_id:54s} ║")
        lines.append(f"╚══════════════════════════════════════════════════════════════════════╝\n")
        
        lines.append(f"Total Decisions: {len(decisions)}\n")
        
        for i, record in enumerate(decisions, 1):
            lines.append(f"\n{'='*70}")
            lines.append(f"Decision {i}/{len(decisions)}")
            lines.append(f"{'='*70}")
            lines.append(record.to_human_readable())
        
        # Summary statistics
        lines.append(f"\n{'='*70}")
        lines.append(f"SUMMARY STATISTICS")
        lines.append(f"{'='*70}")
        
        avg_confidence = sum(d.confidence for d in decisions if d.confidence) / len(decisions)
        lines.append(f"Average Confidence: {avg_confidence*100:.1f}%")
        
        correct_decisions = sum(1 for d in decisions if d.was_correct is True)
        total_evaluated = sum(1 for d in decisions if d.was_correct is not None)
        if total_evaluated > 0:
            accuracy = (correct_decisions / total_evaluated) * 100
            lines.append(f"Decision Accuracy: {accuracy:.1f}% ({correct_decisions}/{total_evaluated})")
        
        human_overrides = sum(1 for d in decisions if d.human_override)
        lines.append(f"Human Overrides: {human_overrides}")
        
        return "\n".join(lines)


# Example usage demonstrating the decision logging
def demo_decision_logging():
    """Demonstrate decision justification logging."""
    logger_instance = DecisionLogger()
    
    # Example 1: Safety Gate Decision
    with logger_instance.decision_context("safety_gate", "safety-check-001") as ctx:
        ctx.set_context(incident_id="INC-20240115-001", service_name="payment-service")
        
        # Inputs
        ctx.add_input("risk_score", 0.18, "Calculated from patch complexity and scope", source="safety_gate_checker")
        ctx.add_input("test_coverage", 95.0, "Percentage of code covered by generated tests", source="test_generator")
        ctx.add_input("static_analysis", "PASS", "No new vulnerabilities detected", source="sonarqube")
        
        # Factors
        ctx.add_factor("patch_size", "5 lines", 0.3, "Small patch reduces risk")
        ctx.add_factor("dependency_impact", "none", 0.4, "No downstream services affected")
        ctx.add_factor("error_severity", "high", 0.9, "15% error rate is critical")
        
        # Constraints
        ctx.add_constraint("tests_passing", True, "All 3 generated tests passed", blocking=True)
        ctx.add_constraint("no_syntax_errors", True, "Patch compiles successfully", blocking=True)
        ctx.add_constraint("business_hours", True, "Change allowed during business hours (10am-6pm)", blocking=False)
        
        # Alternatives
        ctx.add_alternative(
            option="proceed_with_deployment",
            score=0.92,
            pros=["High urgency", "Low risk", "All tests pass"],
            cons=["Minor: during business hours"],
            rejected_reason=None  # This is the chosen option
        )
        
        ctx.add_alternative(
            option="wait_for_manual_review",
            score=0.45,
            pros=["Extra validation", "Human oversight"],
            cons=["45 min delay", "Error rate remains high", "Low risk doesn't justify delay"],
            rejected_reason="Unnecessary delay given low risk score (0.18) and passing tests"
        )
        
        ctx.add_alternative(
            option="rollback_previous_change",
            score=0.12,
            pros=["Immediate action"],
            cons=["No previous deployment to rollback", "Doesn't address root cause"],
            rejected_reason="No recent deployment detected; error pre-dates any changes"
        )
        
        # Record decision
        ctx.record_decision(
            decision="proceed_with_deployment",
            reasoning="""
Risk assessment: LOW (0.18/1.0)
- Small, localized change (5 lines, single method)
- All tests passing (3/3 generated tests, 95% coverage)
- No syntax errors or vulnerabilities
- No downstream service impact

Error severity: CRITICAL (15.2% error rate)
- Exceeds threshold by 10.2 percentage points
- Affecting customer transactions

Trade-off analysis:
- Delay cost: 45 minutes of continued errors = ~4,500 failed transactions
- Risk of bad fix: 0.18 (low) with mitigation via canary deployment
- Decision: Proceed with deployment given high urgency and low risk
            """.strip(),
            confidence=0.92,
            alternatives_considered=["proceed", "manual_review", "rollback"]
        )
    
    # Print the decision
    print("\nExample Decision Log:\n")
    logger_instance.print_decision("safety-check-001")
    
    # Simulate outcome
    decisions = logger_instance.get_decisions(decision_type=DecisionType.SAFETY_GATE)
    if decisions:
        decisions[0].outcome = "Deployment successful, error rate reduced to 0.3%"
        decisions[0].was_correct = True
        decisions[0].outcome_timestamp = datetime.now()
    
    # Generate report
    print("\n\nFull Incident Report:\n")
    report = logger_instance.generate_report("INC-20240115-001")
    print(report)


if __name__ == "__main__":
    demo_decision_logging()
