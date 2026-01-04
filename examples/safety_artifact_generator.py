"""
Proof of Safety Artifact Generator
Implements Improvement #4: "Proof of Safety" Artifact for audit and rollback.
Generates comprehensive safety_report.json with all evidence.
"""

import json
import hashlib
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict


@dataclass
class SafetyArtifact:
    """
    Proof of Safety artifact for audit trail.
    Improvement #4: This becomes audit evidence and rollback reference.
    """
    # Identifiers
    incident_id: str
    service_name: str
    timestamp: str
    
    # Checks performed
    checks_run: List[str]
    checks_passed: List[str]
    checks_failed: List[str]
    
    # Tool versions (deterministic builds)
    tool_versions: Dict[str, str]
    
    # Results
    test_result: Optional[Dict[str, Any]]
    lint_result: Optional[Dict[str, Any]]
    analysis_result: Optional[Dict[str, Any]]
    build_result: Optional[Dict[str, Any]]
    risk_assessment: Optional[Dict[str, Any]]
    
    # Decision
    overall_passed: bool
    recommendation: str
    
    # Audit trail
    commit_hash: str
    build_hash: str
    artifact_hash: str  # Hash of this artifact for integrity
    
    # System identity
    signer: str
    environment: str


class SafetyArtifactGenerator:
    """
    Generates proof of safety artifacts for audit and rollback.
    Improvement #4: Comprehensive audit evidence.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.output_dir = Path(self.config.get('output_dir', '.safety_reports'))
        self.output_dir.mkdir(exist_ok=True)
        
        self.signer = self.config.get('signer', 'safety-gate-system')
        self.environment = self.config.get('environment', 'production')
    
    def generate_artifact(
        self,
        incident_id: str,
        service_name: str,
        checks_run: List[str],
        checks_passed: List[str],
        checks_failed: List[str],
        test_result: Optional[Dict[str, Any]],
        lint_result: Optional[Dict[str, Any]],
        analysis_result: Optional[Dict[str, Any]],
        build_result: Optional[Dict[str, Any]],
        risk_assessment: Optional[Dict[str, Any]],
        overall_passed: bool,
        recommendation: str,
        commit_hash: str
    ) -> SafetyArtifact:
        """
        Generate comprehensive safety artifact.
        
        This artifact includes:
        - All checks run and their results
        - Tool versions for reproducibility
        - Commit and build hashes
        - Decision and reasoning
        - System signature
        """
        timestamp = datetime.utcnow().isoformat() + 'Z'
        
        # Extract tool versions from build result
        tool_versions = {}
        if build_result:
            tool_versions = build_result.get('tool_versions', {})
        
        # Get build hash
        build_hash = build_result.get('build_hash', '') if build_result else ''
        
        # Create artifact
        artifact = SafetyArtifact(
            incident_id=incident_id,
            service_name=service_name,
            timestamp=timestamp,
            checks_run=checks_run,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            tool_versions=tool_versions,
            test_result=test_result,
            lint_result=lint_result,
            analysis_result=analysis_result,
            build_result=build_result,
            risk_assessment=risk_assessment,
            overall_passed=overall_passed,
            recommendation=recommendation,
            commit_hash=commit_hash,
            build_hash=build_hash,
            artifact_hash='',  # Will be calculated
            signer=self.signer,
            environment=self.environment
        )
        
        # Calculate artifact hash for integrity verification
        artifact.artifact_hash = self._calculate_artifact_hash(artifact)
        
        return artifact
    
    def save_artifact(self, artifact: SafetyArtifact) -> Path:
        """
        Save artifact to disk as JSON.
        Returns path to saved file.
        """
        filename = f"safety_report_{artifact.incident_id}_{artifact.timestamp.replace(':', '-')}.json"
        filepath = self.output_dir / filename
        
        # Convert to dict
        artifact_dict = asdict(artifact)
        
        # Save as pretty-printed JSON
        with open(filepath, 'w') as f:
            json.dump(artifact_dict, f, indent=2, sort_keys=True)
        
        return filepath
    
    def load_artifact(self, filepath: Path) -> SafetyArtifact:
        """Load and verify artifact from disk"""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Verify integrity
        stored_hash = data.get('artifact_hash')
        data['artifact_hash'] = ''  # Clear for recalculation
        
        artifact = SafetyArtifact(**data)
        calculated_hash = self._calculate_artifact_hash(artifact)
        
        if stored_hash != calculated_hash:
            raise ValueError(f"Artifact integrity check failed for {filepath}")
        
        artifact.artifact_hash = stored_hash
        return artifact
    
    def _calculate_artifact_hash(self, artifact: SafetyArtifact) -> str:
        """Calculate hash of artifact for integrity verification"""
        # Create a copy without the hash field
        artifact_copy = asdict(artifact)
        artifact_copy['artifact_hash'] = ''
        
        # Calculate SHA256
        content = json.dumps(artifact_copy, sort_keys=True).encode('utf-8')
        return hashlib.sha256(content).hexdigest()
    
    def format_artifact_summary(self, artifact: SafetyArtifact) -> str:
        """Format artifact as human-readable summary"""
        lines = []
        lines.append("=" * 80)
        lines.append("PROOF OF SAFETY ARTIFACT")
        lines.append("=" * 80)
        lines.append(f"Incident ID: {artifact.incident_id}")
        lines.append(f"Service: {artifact.service_name}")
        lines.append(f"Timestamp: {artifact.timestamp}")
        lines.append(f"Environment: {artifact.environment}")
        lines.append(f"Signed by: {artifact.signer}")
        lines.append("")
        
        lines.append("Decision:")
        lines.append(f"  Overall: {'✓ PASSED' if artifact.overall_passed else '✗ FAILED'}")
        lines.append(f"  Recommendation: {artifact.recommendation}")
        lines.append("")
        
        lines.append("Checks Performed:")
        lines.append(f"  Total: {len(artifact.checks_run)}")
        lines.append(f"  Passed: {len(artifact.checks_passed)}")
        lines.append(f"  Failed: {len(artifact.checks_failed)}")
        if artifact.checks_passed:
            for check in artifact.checks_passed:
                lines.append(f"    ✓ {check}")
        if artifact.checks_failed:
            for check in artifact.checks_failed:
                lines.append(f"    ✗ {check}")
        lines.append("")
        
        lines.append("Tool Versions (Deterministic):")
        for tool, version in artifact.tool_versions.items():
            lines.append(f"  {tool}: {version}")
        lines.append("")
        
        lines.append("Commit Information:")
        lines.append(f"  Commit hash: {artifact.commit_hash}")
        lines.append(f"  Build hash: {artifact.build_hash}")
        lines.append(f"  Artifact hash: {artifact.artifact_hash[:16]}...")
        lines.append("")
        
        if artifact.risk_assessment:
            lines.append("Risk Assessment:")
            lines.append(f"  Risk level: {artifact.risk_assessment.get('overall_risk', 'unknown')}")
            lines.append(f"  Risk score: {artifact.risk_assessment.get('risk_score', 0):.1f}/100")
        
        lines.append("=" * 80)
        return "\n".join(lines)


# Example usage
if __name__ == "__main__":
    generator = SafetyArtifactGenerator(config={
        'output_dir': '.safety_reports',
        'signer': 'self-healing-system',
        'environment': 'production'
    })
    
    # Generate artifact
    artifact = generator.generate_artifact(
        incident_id='INC-001',
        service_name='payment-service',
        checks_run=['tests', 'linting', 'security', 'build'],
        checks_passed=['tests', 'linting', 'build'],
        checks_failed=['security'],
        test_result={
            'passed': True,
            'tests_run': 127,
            'tests_passed': 127,
            'coverage_percentage': 85.3
        },
        lint_result={
            'passed': True,
            'errors': 0,
            'warnings': 5
        },
        analysis_result={
            'passed': False,
            'security_scan_passed': False,
            'critical': 1,
            'secrets_found': 1
        },
        build_result={
            'passed': True,
            'build_hash': 'abc123def456',
            'tool_versions': {
                'python': '3.11.0',
                'pip': '23.0.1'
            }
        },
        risk_assessment={
            'overall_risk': 'high',
            'risk_score': 78.5,
            'recommendation': 'MANUAL_REVIEW'
        },
        overall_passed=False,
        recommendation='MANUAL_REVIEW',
        commit_hash='def456abc789'
    )
    
    # Save artifact
    filepath = generator.save_artifact(artifact)
    print(f"Artifact saved to: {filepath}")
    print()
    
    # Display summary
    print(generator.format_artifact_summary(artifact))
    print()
    
    # Verify artifact can be loaded
    loaded = generator.load_artifact(filepath)
    print(f"✓ Artifact loaded and verified (hash: {loaded.artifact_hash[:16]}...)")
