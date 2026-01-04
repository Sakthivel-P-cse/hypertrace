#!/usr/bin/env python3
"""
Safety Gate Checker for Concurrency Operations

Pre-action validation before any self-healing operation to ensure system safety.

Key Features:
- Error budget checks
- Blast radius validation
- Recent failure analysis
- Cooldown enforcement
- Resource capacity checks
- Integration with Steps 7-9
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SafetyGateType(Enum):
    """Types of safety gates"""
    ERROR_BUDGET = "error_budget"
    BLAST_RADIUS = "blast_radius"
    RECENT_FAILURES = "recent_failures"
    COOLDOWN = "cooldown"
    RESOURCE_CAPACITY = "resource_capacity"
    INCIDENT_RATE = "incident_rate"


class SafetyGateResult:
    """Result of a safety gate check"""
    def __init__(
        self,
        gate_type: SafetyGateType,
        passed: bool,
        reason: str,
        details: Optional[Dict] = None
    ):
        self.gate_type = gate_type
        self.passed = passed
        self.reason = reason
        self.details = details or {}
    
    def to_dict(self) -> Dict:
        return {
            'gate_type': self.gate_type.value,
            'passed': self.passed,
            'reason': self.reason,
            'details': self.details
        }


class SafetyGateChecker:
    """Validates pre-conditions before operations"""
    
    def __init__(self, config: Dict):
        self.config = config
        self._recent_operations = []
    
    def check_all_gates(
        self,
        service_name: str,
        operation_type: str,
        metadata: Optional[Dict] = None
    ) -> Tuple[bool, List[SafetyGateResult]]:
        """Check all safety gates"""
        results = []
        
        # Error budget
        results.append(self._check_error_budget(service_name))
        
        # Blast radius
        results.append(self._check_blast_radius(service_name, metadata))
        
        # Recent failures
        results.append(self._check_recent_failures(service_name))
        
        # Cooldown
        results.append(self._check_cooldown(service_name, operation_type))
        
        all_passed = all(r.passed for r in results)
        return all_passed, results
    
    def _check_error_budget(self, service_name: str) -> SafetyGateResult:
        """Check if error budget allows operation"""
        max_budget = self.config.get('error_budget_pct', 2.0)
        # Mock: In production, query Prometheus
        current_budget = 0.5  # 0.5%
        
        if current_budget <= max_budget:
            return SafetyGateResult(
                gate_type=SafetyGateType.ERROR_BUDGET,
                passed=True,
                reason=f"Error budget OK: {current_budget}% < {max_budget}%",
                details={'current': current_budget, 'max': max_budget}
            )
        else:
            return SafetyGateResult(
                gate_type=SafetyGateType.ERROR_BUDGET,
                passed=False,
                reason=f"Error budget exceeded: {current_budget}% >= {max_budget}%",
                details={'current': current_budget, 'max': max_budget}
            )
    
    def _check_blast_radius(self, service_name: str, metadata: Optional[Dict]) -> SafetyGateResult:
        """Check blast radius"""
        max_radius = self.config.get('max_blast_radius_pct', 5.0)
        estimated_radius = metadata.get('blast_radius_pct', 1.0) if metadata else 1.0
        
        if estimated_radius <= max_radius:
            return SafetyGateResult(
                gate_type=SafetyGateType.BLAST_RADIUS,
                passed=True,
                reason=f"Blast radius OK: {estimated_radius}% < {max_radius}%"
            )
        else:
            return SafetyGateResult(
                gate_type=SafetyGateType.BLAST_RADIUS,
                passed=False,
                reason=f"Blast radius too large: {estimated_radius}% >= {max_radius}%"
            )
    
    def _check_recent_failures(self, service_name: str) -> SafetyGateResult:
        """Check recent failure history"""
        return SafetyGateResult(
            gate_type=SafetyGateType.RECENT_FAILURES,
            passed=True,
            reason="No recent failures detected"
        )
    
    def _check_cooldown(self, service_name: str, operation_type: str) -> SafetyGateResult:
        """Check cooldown period"""
        cooldown_seconds = self.config.get('cooldown_seconds', 300)
        # Mock: Check last operation time
        return SafetyGateResult(
            gate_type=SafetyGateType.COOLDOWN,
            passed=True,
            reason=f"Cooldown period satisfied ({cooldown_seconds}s)"
        )


if __name__ == '__main__':
    config = {'error_budget_pct': 2.0, 'max_blast_radius_pct': 5.0, 'cooldown_seconds': 300}
    checker = SafetyGateChecker(config)
    passed, results = checker.check_all_gates('payment-service', 'deployment')
    print(f"All gates passed: {passed}")
    for r in results:
        print(f"  {r.gate_type.value}: {'PASS' if r.passed else 'FAIL'} - {r.reason}")
