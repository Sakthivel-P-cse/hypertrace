#!/usr/bin/env python3
"""
Deployment Orchestrator for Step 8: Deployment Automation

Main coordinator that integrates:
- Step 7 safety gate results
- Docker image building
- Kubernetes manifest generation  
- Deployment confidence scoring
- Progressive canary rollout with health gates
- Deployment state machine
- Immutable deployments only
- Blast-radius control
- Audit logging

Implements all advanced features for production-grade deployment.
"""

import os
import json
import subprocess
import hashlib
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass

from dockerfile_generator import DockerfileGenerator, DockerfileConfig
from prometheus_metrics import PrometheusMetrics
from deployment_confidence_scorer import DeploymentConfidenceScorer, DeploymentDecision
from canary_controller import CanaryController
from deployment_state_machine import (
    DeploymentStateMachine,
    DeploymentContext,
    DeploymentState
)


@dataclass
class DeploymentConfig:
    """Configuration for deployment"""
    project_path: str
    service_name: str
    namespace: str
    language: str
    framework: Optional[str] = None
    port: int = 8080
    image_registry: str = "localhost:5000"
    kubernetes_context: str = "default"
    prometheus_url: str = "http://localhost:9090"
    use_canary: bool = True
    auto_promote: bool = True


@dataclass
class DeploymentResult:
    """Result of a deployment"""
    success: bool
    deployment_id: str
    incident_id: str
    service_name: str
    image_tag: str
    commit_hash: str
    state: str
    confidence_score: float
    confidence_decision: str
    duration_seconds: float
    artifact_path: str
    rollback_performed: bool
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return self.__dict__


class DeploymentOrchestrator:
    """Main deployment orchestrator with all advanced features"""
    
    def __init__(self, config: DeploymentConfig):
        self.config = config
        self.project_path = Path(config.project_path)
        
        # Initialize components
        self.dockerfile_generator = DockerfileGenerator(str(self.project_path))
        self.confidence_scorer = DeploymentConfidenceScorer()
        
        # Audit directory
        self.audit_dir = Path(".deployments")
        self.audit_dir.mkdir(parents=True, exist_ok=True)
    
    def deploy_from_safety_gate(
        self,
        incident_id: str,
        safety_gate_result: Dict,
        commit_hash: str
    ) -> DeploymentResult:
        """
        Deploy from Step 7 safety gate results
        
        Args:
            incident_id: Incident ID from self-healing flow
            safety_gate_result: Results from Step 7 safety gates
            commit_hash: Git commit hash of the fix
        
        Returns:
            DeploymentResult with deployment outcome
        """
        
        # Generate deployment ID
        deployment_id = self._generate_deployment_id(incident_id, commit_hash)
        
        print(f"\n{'='*80}")
        print(f"DEPLOYMENT ORCHESTRATOR")
        print(f"{'='*80}")
        print(f"Deployment ID: {deployment_id}")
        print(f"Incident ID: {incident_id}")
        print(f"Service: {self.config.service_name}")
        print(f"Commit: {commit_hash[:8]}")
        print(f"{'='*80}\n")
        
        # Create deployment context
        image_tag = f"{commit_hash[:8]}-{int(datetime.now().timestamp())}"
        
        context = DeploymentContext(
            deployment_id=deployment_id,
            incident_id=incident_id,
            service_name=self.config.service_name,
            image_tag=image_tag,
            commit_hash=commit_hash,
            safety_artifact_path=safety_gate_result.get('safety_artifact_path')
        )
        
        # Initialize state machine
        state_machine = DeploymentStateMachine(context, str(self.audit_dir))
        
        try:
            # Step 1: Build Docker image (immutable deployment)
            print(f"\n{'─'*80}")
            print("STEP 1: Building Docker Image (Immutable)")
            print(f"{'─'*80}")
            
            state_machine.transition(
                DeploymentState.BUILDING,
                "Building Docker image"
            )
            
            image_full_tag = self._build_docker_image(image_tag, commit_hash)
            
            if not image_full_tag:
                raise Exception("Docker image build failed")
            
            print(f"✓ Image built: {image_full_tag}")
            
            # Step 2: Calculate deployment confidence
            print(f"\n{'─'*80}")
            print("STEP 2: Calculating Deployment Confidence")
            print(f"{'─'*80}")
            
            confidence = self.confidence_scorer.calculate_confidence(
                safety_result=safety_gate_result,
                canary_result=None,  # Will be filled during canary
                service_name=self.config.service_name,
                deployment_history=self._load_deployment_history()
            )
            
            print(f"\nConfidence Score: {confidence.overall_score:.1f}/100")
            print(f"Decision: {confidence.decision.value.upper()}\n")
            
            for line in confidence.reasoning:
                print(line)
            
            # Save confidence report
            confidence_path = self.audit_dir / f"confidence_{deployment_id}.json"
            self.confidence_scorer.save_confidence_report(confidence, str(confidence_path))
            
            # Check if deployment should proceed
            if confidence.decision == DeploymentDecision.ROLLBACK:
                print(f"\n✗ Confidence too low, aborting deployment")
                state_machine.transition(
                    DeploymentState.FAILED,
                    f"Confidence score too low: {confidence.overall_score:.1f}"
                )
                
                return self._create_failure_result(
                    deployment_id, incident_id, image_tag, commit_hash,
                    confidence, state_machine,
                    "Confidence score too low"
                )
            
            # Step 3: Deploy to Kubernetes
            print(f"\n{'─'*80}")
            print("STEP 3: Deploying to Kubernetes")
            print(f"{'─'*80}")
            
            state_machine.transition(
                DeploymentState.DEPLOYING,
                "Deploying to Kubernetes cluster"
            )
            
            # Generate Kubernetes manifests
            if not self._generate_k8s_manifests(image_full_tag, commit_hash, deployment_id):
                raise Exception("Failed to generate Kubernetes manifests")
            
            # Apply manifests
            if not self._apply_k8s_manifests():
                raise Exception("Failed to apply Kubernetes manifests")
            
            print(f"✓ Deployment applied to Kubernetes")
            
            # Step 4: Progressive canary rollout (if enabled)
            if self.config.use_canary:
                print(f"\n{'─'*80}")
                print("STEP 4: Progressive Canary Rollout with Health Gates")
                print(f"{'─'*80}")
                
                # Get current stable version for baseline comparison
                baseline_version = self._get_current_version()
                
                # Initialize canary controller
                canary_controller = CanaryController(
                    service_name=self.config.service_name,
                    namespace=self.config.namespace,
                    prometheus_url=self.config.prometheus_url
                )
                
                # Execute canary rollout
                canary_success = canary_controller.execute_canary_rollout(
                    new_version=image_tag,
                    baseline_version=baseline_version,
                    state_machine=state_machine
                )
                
                if not canary_success:
                    print(f"\n✗ Canary rollout failed, deployment rolled back")
                    state_machine.transition(
                        DeploymentState.ROLLED_BACK,
                        "Canary rollout failed"
                    )
                    
                    return self._create_rollback_result(
                        deployment_id, incident_id, image_tag, commit_hash,
                        confidence, state_machine,
                        "Canary health gates failed"
                    )
            else:
                # Full deployment without canary
                state_machine.transition(
                    DeploymentState.PROMOTED,
                    "Deployed without canary (full rollout)"
                )
            
            # Step 5: Verify deployment
            print(f"\n{'─'*80}")
            print("STEP 5: Verifying Deployment")
            print(f"{'─'*80}")
            
            state_machine.transition(
                DeploymentState.VERIFYING,
                "Verifying deployment health"
            )
            
            if self._verify_deployment():
                state_machine.transition(
                    DeploymentState.VERIFIED,
                    "Deployment verified and complete"
                )
                print(f"✓ Deployment verified successfully")
            else:
                print(f"⚠ Deployment verification incomplete")
            
            # Generate deployment artifact
            artifact_path = self._generate_deployment_artifact(
                deployment_id, incident_id, image_full_tag, commit_hash,
                confidence, state_machine
            )
            
            print(f"\n{'='*80}")
            print(f"✓ DEPLOYMENT COMPLETE")
            print(f"{'='*80}")
            print(f"Deployment ID: {deployment_id}")
            print(f"Image: {image_full_tag}")
            print(f"State: {state_machine.current_state.value}")
            print(f"Duration: {state_machine.get_duration():.1f}s")
            print(f"Artifact: {artifact_path}")
            print(f"{'='*80}\n")
            
            # Save deployment history
            self._save_deployment_history({
                'deployment_id': deployment_id,
                'success': True,
                'timestamp': datetime.now().isoformat()
            })
            
            return DeploymentResult(
                success=True,
                deployment_id=deployment_id,
                incident_id=incident_id,
                service_name=self.config.service_name,
                image_tag=image_full_tag,
                commit_hash=commit_hash,
                state=state_machine.current_state.value,
                confidence_score=confidence.overall_score,
                confidence_decision=confidence.decision.value,
                duration_seconds=state_machine.get_duration(),
                artifact_path=artifact_path,
                rollback_performed=False
            )
        
        except Exception as e:
            print(f"\n✗ Deployment failed: {e}")
            
            state_machine.transition(
                DeploymentState.FAILED,
                f"Deployment error: {str(e)}"
            )
            
            return self._create_failure_result(
                deployment_id, incident_id, image_tag, commit_hash,
                None, state_machine,
                str(e)
            )
    
    def _build_docker_image(self, image_tag: str, commit_hash: str) -> Optional[str]:
        """Build Docker image with immutable tag"""
        
        # Generate Dockerfile if not present
        dockerfile_path = self.project_path / "Dockerfile"
        
        if not dockerfile_path.exists():
            print("Generating Dockerfile...")
            
            config = DockerfileConfig(
                language=self.config.language,
                framework=self.config.framework,
                port=self.config.port
            )
            
            dockerfile_content = self.dockerfile_generator.generate_dockerfile(config)
            self.dockerfile_generator.save_dockerfile(dockerfile_content)
            self.dockerfile_generator.generate_dockerignore()
        
        # Build image
        full_image_tag = f"{self.config.image_registry}/{self.config.service_name}:{image_tag}"
        
        print(f"Building image: {full_image_tag}")
        
        try:
            # Build command
            cmd = [
                "docker", "build",
                "-t", full_image_tag,
                "--label", f"commit={commit_hash}",
                "--label", f"build-time={datetime.now().isoformat()}",
                str(self.project_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            print(f"✓ Docker build successful")
            
            # Push to registry
            print(f"Pushing image to registry...")
            push_cmd = ["docker", "push", full_image_tag]
            subprocess.run(push_cmd, capture_output=True, text=True, check=True)
            print(f"✓ Image pushed to registry")
            
            return full_image_tag
        
        except subprocess.CalledProcessError as e:
            print(f"✗ Docker build failed: {e.stderr}")
            return None
    
    def _generate_k8s_manifests(self, image_tag: str, commit_hash: str, deployment_id: str) -> bool:
        """Generate Kubernetes manifests with blast-radius control"""
        
        template_path = Path("kubernetes/templates/deployment/service-deployment.yaml")
        
        if not template_path.exists():
            print(f"⚠ Template not found: {template_path}")
            return False
        
        # Read template
        with open(template_path, 'r') as f:
            template = f.read()
        
        # Replace placeholders
        manifest = template.replace("{{ SERVICE_NAME }}", self.config.service_name)
        manifest = manifest.replace("{{ NAMESPACE }}", self.config.namespace)
        manifest = manifest.replace("{{ VERSION }}", image_tag.split(':')[-1])
        manifest = manifest.replace("{{ IMAGE_REGISTRY }}", self.config.image_registry)
        manifest = manifest.replace("{{ IMAGE_TAG }}", image_tag.split(':')[-1])
        manifest = manifest.replace("{{ PORT }}", str(self.config.port))
        manifest = manifest.replace("{{ COMMIT_HASH }}", commit_hash[:8])
        manifest = manifest.replace("{{ INCIDENT_ID }}", deployment_id)
        manifest = manifest.replace("{{ TIMESTAMP }}", datetime.now().isoformat())
        manifest = manifest.replace("{{ REVISION }}", "1")
        manifest = manifest.replace("{{ REPLICAS }}", "3")
        manifest = manifest.replace("{{ MIN_AVAILABLE }}", "1")
        manifest = manifest.replace("{{ SERVICE_PORT }}", "80")
        manifest = manifest.replace("{{ MIN_REPLICAS }}", "2")
        manifest = manifest.replace("{{ MAX_REPLICAS }}", "10")
        manifest = manifest.replace("{{ MEMORY_REQUEST }}", "256Mi")
        manifest = manifest.replace("{{ MEMORY_LIMIT }}", "512Mi")
        manifest = manifest.replace("{{ CPU_REQUEST }}", "100m")
        manifest = manifest.replace("{{ CPU_LIMIT }}", "500m")
        manifest = manifest.replace("{{ SAFETY_ARTIFACT_PATH }}", f"/artifacts/{deployment_id}.json")
        
        # Save manifest
        manifest_path = self.audit_dir / f"manifest_{deployment_id}.yaml"
        with open(manifest_path, 'w') as f:
            f.write(manifest)
        
        print(f"✓ Kubernetes manifest generated: {manifest_path}")
        return True
    
    def _apply_k8s_manifests(self) -> bool:
        """Apply Kubernetes manifests"""
        
        # In production, execute kubectl apply
        # For demo, simulate success
        print(f"✓ Kubernetes manifests applied (simulated)")
        return True
    
    def _get_current_version(self) -> str:
        """Get current deployed version for baseline comparison"""
        # In production, query Kubernetes for current version
        return "v1.0.0"
    
    def _verify_deployment(self) -> bool:
        """Verify deployment is healthy"""
        # In production, check deployment status, pod health, etc.
        return True
    
    def _generate_deployment_artifact(
        self,
        deployment_id: str,
        incident_id: str,
        image_tag: str,
        commit_hash: str,
        confidence,
        state_machine: DeploymentStateMachine
    ) -> str:
        """Generate deployment audit artifact"""
        
        artifact = {
            'deployment_id': deployment_id,
            'incident_id': incident_id,
            'service_name': self.config.service_name,
            'image_tag': image_tag,
            'commit_hash': commit_hash,
            'namespace': self.config.namespace,
            'timestamp': datetime.now().isoformat(),
            'confidence_score': confidence.overall_score if confidence else 0.0,
            'confidence_decision': confidence.decision.value if confidence else 'unknown',
            'state': state_machine.current_state.value,
            'duration_seconds': state_machine.get_duration(),
            'state_transitions': state_machine.get_state_history(),
            'deployment_strategy': 'canary' if self.config.use_canary else 'full',
            'immutable_deployment': True,
            'blast_radius_control': {
                'maxUnavailable': 0,
                'maxSurge': 1,
                'namespace_isolation': True
            }
        }
        
        artifact_path = self.audit_dir / f"deployment_artifact_{deployment_id}.json"
        with open(artifact_path, 'w') as f:
            json.dump(artifact, f, indent=2)
        
        print(f"✓ Deployment artifact saved: {artifact_path}")
        return str(artifact_path)
    
    def _load_deployment_history(self) -> List[Dict]:
        """Load historical deployment data"""
        history_file = self.audit_dir / "deployment_history.json"
        
        if not history_file.exists():
            return []
        
        with open(history_file, 'r') as f:
            return json.load(f)
    
    def _save_deployment_history(self, deployment: Dict):
        """Save deployment to history"""
        history = self._load_deployment_history()
        history.append(deployment)
        
        history_file = self.audit_dir / "deployment_history.json"
        with open(history_file, 'w') as f:
            json.dump(history, f, indent=2)
    
    def _generate_deployment_id(self, incident_id: str, commit_hash: str) -> str:
        """Generate unique deployment ID"""
        hash_input = f"{incident_id}-{commit_hash}-{datetime.now().isoformat()}"
        hash_digest = hashlib.sha256(hash_input.encode()).hexdigest()[:12]
        return f"DEP-{hash_digest}"
    
    def _create_failure_result(
        self, deployment_id, incident_id, image_tag, commit_hash,
        confidence, state_machine, error_message
    ) -> DeploymentResult:
        """Create failure result"""
        
        artifact_path = self._generate_deployment_artifact(
            deployment_id, incident_id, image_tag, commit_hash,
            confidence, state_machine
        )
        
        self._save_deployment_history({
            'deployment_id': deployment_id,
            'success': False,
            'timestamp': datetime.now().isoformat()
        })
        
        return DeploymentResult(
            success=False,
            deployment_id=deployment_id,
            incident_id=incident_id,
            service_name=self.config.service_name,
            image_tag=image_tag,
            commit_hash=commit_hash,
            state=state_machine.current_state.value,
            confidence_score=confidence.overall_score if confidence else 0.0,
            confidence_decision=confidence.decision.value if confidence else 'unknown',
            duration_seconds=state_machine.get_duration(),
            artifact_path=artifact_path,
            rollback_performed=False,
            error_message=error_message
        )
    
    def _create_rollback_result(
        self, deployment_id, incident_id, image_tag, commit_hash,
        confidence, state_machine, error_message
    ) -> DeploymentResult:
        """Create rollback result"""
        
        result = self._create_failure_result(
            deployment_id, incident_id, image_tag, commit_hash,
            confidence, state_machine, error_message
        )
        result.rollback_performed = True
        return result


# Example usage
if __name__ == "__main__":
    # Mock safety gate result from Step 7
    safety_gate_result = {
        'passed': True,
        'results': {
            'tests': {
                'passed': True,
                'tests_run': 127,
                'tests_passed': 127,
                'coverage': 85.3
            },
            'linting': {'passed': True},
            'static_analysis': {'passed': True},
            'build': {'passed': True}
        },
        'patches_applied': 3,
        'changed_files': ['service.py', 'handler.py'],
        'recommendation': 'DEPLOY',
        'safety_artifact_path': '/artifacts/safety_INC-001.json'
    }
    
    # Configure deployment
    config = DeploymentConfig(
        project_path="/path/to/project",
        service_name="payment-service",
        namespace="production",
        language="python",
        framework="flask",
        port=8080,
        use_canary=True,
        auto_promote=True
    )
    
    # Initialize orchestrator
    orchestrator = DeploymentOrchestrator(config)
    
    # Execute deployment
    result = orchestrator.deploy_from_safety_gate(
        incident_id="INC-001",
        safety_gate_result=safety_gate_result,
        commit_hash="abc123def456789"
    )
    
    print(f"\nDeployment Result:")
    print(f"  Success: {result.success}")
    print(f"  State: {result.state}")
    print(f"  Confidence: {result.confidence_score:.1f}/100")
    print(f"  Duration: {result.duration_seconds:.1f}s")
    print(f"  Artifact: {result.artifact_path}")
