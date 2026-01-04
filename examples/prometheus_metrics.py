#!/usr/bin/env python3
"""
Prometheus Metrics Integration for Step 8: Deployment Automation

Queries Prometheus for metric-driven health gates during canary rollout.
Implements progressive health checks as per Google SRE best practices.
"""

import requests
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class MetricStatus(Enum):
    """Metric evaluation status"""
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


@dataclass
class MetricGate:
    """Definition of a health gate metric"""
    name: str
    query: str
    threshold: float
    operator: str  # 'lt', 'le', 'gt', 'ge', 'eq'
    description: str
    severity: str = "critical"  # critical, high, medium, low


@dataclass
class MetricResult:
    """Result of a metric evaluation"""
    gate: MetricGate
    current_value: float
    baseline_value: Optional[float]
    status: MetricStatus
    message: str
    timestamp: datetime


@dataclass
class HealthGateResult:
    """Overall health gate evaluation result"""
    passed: bool
    total_gates: int
    passed_gates: int
    failed_gates: int
    metric_results: List[MetricResult]
    evaluation_time: datetime
    duration_seconds: float


class PrometheusMetrics:
    """Query Prometheus for deployment health metrics"""
    
    def __init__(self, prometheus_url: str = "http://localhost:9090"):
        self.prometheus_url = prometheus_url.rstrip('/')
        self.api_url = f"{self.prometheus_url}/api/v1"
    
    def query(self, query: str, time: Optional[datetime] = None) -> Dict:
        """Execute a Prometheus query"""
        
        params = {'query': query}
        if time:
            params['time'] = time.isoformat()
        
        try:
            response = requests.get(
                f"{self.api_url}/query",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            if data['status'] != 'success':
                raise Exception(f"Prometheus query failed: {data}")
            
            return data['data']
        
        except Exception as e:
            print(f"⚠ Prometheus query error: {e}")
            return {'resultType': 'vector', 'result': []}
    
    def query_range(self, query: str, start: datetime, end: datetime, step: str = "15s") -> Dict:
        """Execute a Prometheus range query"""
        
        params = {
            'query': query,
            'start': start.isoformat(),
            'end': end.isoformat(),
            'step': step
        }
        
        try:
            response = requests.get(
                f"{self.api_url}/query_range",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            if data['status'] != 'success':
                raise Exception(f"Prometheus range query failed: {data}")
            
            return data['data']
        
        except Exception as e:
            print(f"⚠ Prometheus range query error: {e}")
            return {'resultType': 'matrix', 'result': []}
    
    def get_metric_value(self, query: str) -> Optional[float]:
        """Get single metric value from query"""
        
        data = self.query(query)
        
        if data['resultType'] == 'vector' and len(data['result']) > 0:
            return float(data['result'][0]['value'][1])
        
        return None
    
    def get_error_rate(self, service: str, version: str, duration: str = "5m") -> Optional[float]:
        """Get error rate for a service version"""
        
        query = f"""
        sum(rate(http_requests_total{{service="{service}",version="{version}",status=~"5.."}}[{duration}])) /
        sum(rate(http_requests_total{{service="{service}",version="{version}"}}[{duration}]))
        """
        
        return self.get_metric_value(query)
    
    def get_latency_percentile(self, service: str, version: str, percentile: int = 95, duration: str = "5m") -> Optional[float]:
        """Get latency percentile for a service version"""
        
        query = f"""
        histogram_quantile(
          {percentile / 100},
          sum(rate(http_request_duration_seconds_bucket{{service="{service}",version="{version}"}}[{duration}])) by (le)
        )
        """
        
        return self.get_metric_value(query)
    
    def get_saturation(self, service: str, version: str) -> Optional[float]:
        """Get resource saturation (CPU usage)"""
        
        query = f"""
        avg(rate(container_cpu_usage_seconds_total{{service="{service}",version="{version}"}}[5m]))
        """
        
        return self.get_metric_value(query)
    
    def get_baseline_metric(self, service: str, baseline_version: str, metric_query: str) -> Optional[float]:
        """Get baseline metric value from stable version"""
        
        # Replace version placeholder in query
        query = metric_query.replace("{version}", baseline_version)
        return self.get_metric_value(query)


class HealthGateEvaluator:
    """Evaluate health gates for canary deployments"""
    
    def __init__(self, prometheus: PrometheusMetrics):
        self.prometheus = prometheus
    
    def create_standard_gates(self, service: str) -> List[MetricGate]:
        """Create standard health gates based on Google SRE practices"""
        
        gates = [
            MetricGate(
                name="error_rate",
                query=f'sum(rate(http_requests_total{{service="{service}",version="{{version}}",status=~"5.."}}[5m])) / sum(rate(http_requests_total{{service="{service}",version="{{version}}"}}[5m]))',
                threshold=1.1,  # 110% of baseline
                operator="lt",
                description="Error rate must be < 110% of baseline",
                severity="critical"
            ),
            MetricGate(
                name="p95_latency",
                query=f'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{{service="{service}",version="{{version}}"}}[5m])) by (le))',
                threshold=0.5,  # 500ms
                operator="lt",
                description="P95 latency must be < 500ms",
                severity="critical"
            ),
            MetricGate(
                name="p99_latency",
                query=f'histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{{service="{service}",version="{{version}}"}}[5m])) by (le))',
                threshold=1.0,  # 1s
                operator="lt",
                description="P99 latency must be < 1s",
                severity="high"
            ),
            MetricGate(
                name="cpu_saturation",
                query=f'avg(rate(container_cpu_usage_seconds_total{{service="{service}",version="{{version}}"}}[5m]))',
                threshold=0.8,  # 80% CPU
                operator="lt",
                description="CPU usage must be < 80%",
                severity="high"
            ),
            MetricGate(
                name="memory_usage",
                query=f'avg(container_memory_usage_bytes{{service="{service}",version="{{version}}"}}) / avg(container_spec_memory_limit_bytes{{service="{service}",version="{{version}}"}})',
                threshold=0.9,  # 90% memory
                operator="lt",
                description="Memory usage must be < 90%",
                severity="medium"
            ),
            MetricGate(
                name="request_rate_drop",
                query=f'sum(rate(http_requests_total{{service="{service}",version="{{version}}"}}[5m]))',
                threshold=0.5,  # At least 50% of baseline
                operator="gt",
                description="Request rate must be > 50% of baseline",
                severity="medium"
            )
        ]
        
        return gates
    
    def evaluate_gate(
        self,
        gate: MetricGate,
        version: str,
        baseline_version: Optional[str] = None
    ) -> MetricResult:
        """Evaluate a single health gate"""
        
        # Replace version in query
        query = gate.query.replace("{version}", version)
        
        # Get current value
        current_value = self.prometheus.get_metric_value(query)
        
        if current_value is None:
            return MetricResult(
                gate=gate,
                current_value=0.0,
                baseline_value=None,
                status=MetricStatus.UNKNOWN,
                message=f"Failed to query metric: {gate.name}",
                timestamp=datetime.now()
            )
        
        # Get baseline value if available
        baseline_value = None
        if baseline_version:
            baseline_query = gate.query.replace("{version}", baseline_version)
            baseline_value = self.prometheus.get_metric_value(baseline_query)
        
        # Adjust threshold for baseline-relative gates
        threshold = gate.threshold
        if baseline_value is not None and gate.operator in ['lt', 'le']:
            # For relative thresholds (e.g., error_rate < baseline * 1.1)
            if gate.name == "error_rate":
                threshold = baseline_value * gate.threshold
        
        # Evaluate condition
        passed = self._evaluate_condition(current_value, threshold, gate.operator)
        
        status = MetricStatus.PASS if passed else MetricStatus.FAIL
        
        message = self._format_message(gate, current_value, threshold, baseline_value, passed)
        
        return MetricResult(
            gate=gate,
            current_value=current_value,
            baseline_value=baseline_value,
            status=status,
            message=message,
            timestamp=datetime.now()
        )
    
    def _evaluate_condition(self, value: float, threshold: float, operator: str) -> bool:
        """Evaluate metric condition"""
        
        if operator == 'lt':
            return value < threshold
        elif operator == 'le':
            return value <= threshold
        elif operator == 'gt':
            return value > threshold
        elif operator == 'ge':
            return value >= threshold
        elif operator == 'eq':
            return abs(value - threshold) < 0.001
        else:
            return False
    
    def _format_message(
        self,
        gate: MetricGate,
        current: float,
        threshold: float,
        baseline: Optional[float],
        passed: bool
    ) -> str:
        """Format result message"""
        
        status_icon = "✓" if passed else "✗"
        
        msg = f"{status_icon} {gate.name}: {current:.4f}"
        
        if baseline is not None:
            msg += f" (baseline: {baseline:.4f})"
        
        msg += f" | threshold: {gate.operator} {threshold:.4f}"
        
        if not passed:
            msg += f" | FAILED: {gate.description}"
        
        return msg
    
    def evaluate_all_gates(
        self,
        gates: List[MetricGate],
        version: str,
        baseline_version: Optional[str] = None
    ) -> HealthGateResult:
        """Evaluate all health gates"""
        
        start_time = time.time()
        
        results = []
        for gate in gates:
            result = self.evaluate_gate(gate, version, baseline_version)
            results.append(result)
        
        passed_count = sum(1 for r in results if r.status == MetricStatus.PASS)
        failed_count = sum(1 for r in results if r.status == MetricStatus.FAIL)
        
        # Check critical failures
        critical_failures = [
            r for r in results
            if r.status == MetricStatus.FAIL and r.gate.severity == "critical"
        ]
        
        overall_passed = len(critical_failures) == 0 and failed_count == 0
        
        duration = time.time() - start_time
        
        return HealthGateResult(
            passed=overall_passed,
            total_gates=len(gates),
            passed_gates=passed_count,
            failed_gates=failed_count,
            metric_results=results,
            evaluation_time=datetime.now(),
            duration_seconds=duration
        )
    
    def wait_for_metrics(self, service: str, version: str, wait_seconds: int = 60):
        """Wait for metrics to be available"""
        
        print(f"⏳ Waiting {wait_seconds}s for metrics to stabilize...")
        
        query = f'sum(rate(http_requests_total{{service="{service}",version="{version}"}}[1m]))'
        
        for i in range(wait_seconds):
            value = self.prometheus.get_metric_value(query)
            if value is not None and value > 0:
                print(f"✓ Metrics available after {i+1}s")
                return True
            time.sleep(1)
        
        print("⚠ Timeout waiting for metrics")
        return False


# Example usage
if __name__ == "__main__":
    # Initialize Prometheus client
    prometheus = PrometheusMetrics("http://localhost:9090")
    
    # Create evaluator
    evaluator = HealthGateEvaluator(prometheus)
    
    # Create standard gates
    gates = evaluator.create_standard_gates("payment-service")
    
    # Evaluate gates for canary version
    result = evaluator.evaluate_all_gates(
        gates=gates,
        version="v2.1.0-abc123",
        baseline_version="v2.0.0"
    )
    
    print(f"\n{'='*80}")
    print(f"HEALTH GATE EVALUATION")
    print(f"{'='*80}")
    print(f"Status: {'✓ PASSED' if result.passed else '✗ FAILED'}")
    print(f"Gates: {result.passed_gates}/{result.total_gates} passed")
    print(f"Duration: {result.duration_seconds:.2f}s")
    print(f"\nResults:")
    
    for metric_result in result.metric_results:
        print(f"  {metric_result.message}")
