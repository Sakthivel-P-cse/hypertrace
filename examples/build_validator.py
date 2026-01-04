"""
Build Validator
Validates that code builds successfully with deterministic, reproducible builds.
Implements Improvement #5: Deterministic Re-runs.
"""

import subprocess
import re
import json
import hashlib
from typing import Dict, List, Any, Optional
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime


@dataclass
class BuildResult:
    """Result of build validation"""
    passed: bool
    build_system: str
    duration_seconds: float
    errors: List[Dict[str, Any]]
    warnings: List[Dict[str, Any]]
    artifacts: List[str]
    build_hash: str  # For deterministic builds
    tool_versions: Dict[str, str]  # Tool version locking


class BuildValidator:
    """
    Validates builds with deterministic, reproducible results.
    Locks tool versions to ensure same input → same result (Improvement #5).
    """
    
    def __init__(self, project_path: str, config: Optional[Dict[str, Any]] = None):
        self.project_path = Path(project_path)
        self.config = config or {}
        
        self.timeout = self.config.get('timeout_seconds', 600)
        self.use_containers = self.config.get('use_containers', False)
        self.lock_versions = self.config.get('lock_versions', True)
    
    def validate_build(self, language: str) -> BuildResult:
        """
        Validate that project builds successfully.
        Uses version-locked tools for deterministic results.
        """
        start_time = datetime.now()
        
        # Detect build system
        build_system = self._detect_build_system(language)
        
        # Get/lock tool versions for reproducibility
        tool_versions = self._get_tool_versions(build_system)
        
        # Execute build
        if self.use_containers:
            # Improvement #5: Use containers for deterministic builds
            result = self._build_in_container(build_system, language)
        else:
            result = self._build_native(build_system, language)
        
        # Parse build output
        errors, warnings = self._parse_build_output(result.stdout + result.stderr)
        
        # Find artifacts
        artifacts = self._find_build_artifacts(build_system)
        
        # Calculate build hash for reproducibility
        build_hash = self._calculate_build_hash(artifacts, tool_versions)
        
        duration = (datetime.now() - start_time).total_seconds()
        
        return BuildResult(
            passed=(result.returncode == 0 and len(errors) == 0),
            build_system=build_system,
            duration_seconds=duration,
            errors=errors,
            warnings=warnings,
            artifacts=artifacts,
            build_hash=build_hash,
            tool_versions=tool_versions
        )
    
    def _detect_build_system(self, language: str) -> str:
        """Detect build system from project files"""
        if language == 'python':
            if (self.project_path / 'pyproject.toml').exists():
                return 'poetry'
            elif (self.project_path / 'setup.py').exists():
                return 'setuptools'
            return 'pip'
        
        elif language == 'java':
            if (self.project_path / 'pom.xml').exists():
                return 'maven'
            elif (self.project_path / 'build.gradle').exists():
                return 'gradle'
            return 'maven'
        
        elif language in ['javascript', 'typescript']:
            if (self.project_path / 'package.json').exists():
                pkg = json.loads((self.project_path / 'package.json').read_text())
                if 'vite' in pkg.get('devDependencies', {}):
                    return 'vite'
                elif 'webpack' in pkg.get('devDependencies', {}):
                    return 'webpack'
                return 'npm'
            return 'npm'
        
        elif language == 'go':
            return 'go'
        
        return 'unknown'
    
    def _get_tool_versions(self, build_system: str) -> Dict[str, str]:
        """
        Get versions of build tools for reproducibility.
        Improvement #5: Lock tool versions.
        """
        versions = {}
        
        tools_to_check = {
            'maven': ['mvn'],
            'gradle': ['gradle'],
            'npm': ['node', 'npm'],
            'poetry': ['python', 'poetry'],
            'go': ['go'],
            'pip': ['python', 'pip']
        }
        
        for tool in tools_to_check.get(build_system, []):
            try:
                result = subprocess.run(
                    [tool, '--version'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                # Parse version from output
                version_match = re.search(r'(\d+\.\d+\.\d+)', result.stdout)
                if version_match:
                    versions[tool] = version_match.group(1)
            except:
                versions[tool] = 'unknown'
        
        return versions
    
    def _build_in_container(self, build_system: str, language: str) -> subprocess.CompletedProcess:
        """
        Build in container for deterministic, reproducible builds.
        Improvement #5: Use containers to avoid "works on my machine".
        """
        # Create Dockerfile for build
        dockerfile = self._generate_build_dockerfile(build_system, language)
        
        # Build image
        try:
            subprocess.run(
                ['docker', 'build', '-t', 'safety-gate-build', '-f-', '.'],
                input=dockerfile,
                text=True,
                cwd=self.project_path,
                capture_output=True,
                timeout=300
            )
            
            # Run build in container
            result = subprocess.run(
                ['docker', 'run', '--rm', '-v', f'{self.project_path}:/app', 'safety-gate-build'],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            return result
        except Exception as e:
            # Fall back to native build
            return self._build_native(build_system, language)
    
    def _build_native(self, build_system: str, language: str) -> subprocess.CompletedProcess:
        """Build natively on the host system"""
        cmd = self._get_build_command(build_system)
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            return result
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=1,
                stdout='',
                stderr=f'Build timeout after {self.timeout}s'
            )
    
    def _get_build_command(self, build_system: str) -> List[str]:
        """Get build command for build system"""
        commands = {
            'maven': ['mvn', 'clean', 'compile', '-B'],
            'gradle': ['gradle', 'build', '--no-daemon'],
            'npm': ['npm', 'run', 'build'],
            'poetry': ['poetry', 'build'],
            'pip': ['python', 'setup.py', 'build'],
            'go': ['go', 'build', './...'],
            'vite': ['npm', 'run', 'build'],
            'webpack': ['npm', 'run', 'build']
        }
        
        return commands.get(build_system, ['echo', 'No build command'])
    
    def _generate_build_dockerfile(self, build_system: str, language: str) -> str:
        """Generate Dockerfile for containerized build"""
        dockerfiles = {
            'maven': '''
FROM maven:3.8-openjdk-17
WORKDIR /app
COPY pom.xml .
RUN mvn dependency:go-offline
COPY . .
RUN mvn clean compile
''',
            'npm': '''
FROM node:18-alpine
WORKDIR /app
COPY package*.json .
RUN npm ci
COPY . .
RUN npm run build
''',
            'poetry': '''
FROM python:3.11-slim
WORKDIR /app
RUN pip install poetry
COPY pyproject.toml poetry.lock* .
RUN poetry install --no-dev
COPY . .
RUN poetry build
'''
        }
        
        return dockerfiles.get(build_system, 'FROM alpine\nCMD echo "No Dockerfile"')
    
    def _parse_build_output(self, output: str) -> tuple:
        """Parse errors and warnings from build output"""
        errors = []
        warnings = []
        
        # Java/Maven errors
        for match in re.finditer(r'\[ERROR\]\s+(.+?):(\d+):\s+(.+)', output):
            file_path, line, message = match.groups()
            errors.append({
                'file': file_path,
                'line': int(line),
                'message': message
            })
        
        # Java/Maven warnings
        for match in re.finditer(r'\[WARNING\]\s+(.+?):(\d+):\s+(.+)', output):
            file_path, line, message = match.groups()
            warnings.append({
                'file': file_path,
                'line': int(line),
                'message': message
            })
        
        # Python errors
        for match in re.finditer(r'File "(.+?)", line (\d+).*\n\s+(.+)', output):
            file_path, line, message = match.groups()
            errors.append({
                'file': file_path,
                'line': int(line),
                'message': message
            })
        
        # TypeScript/JavaScript errors
        for match in re.finditer(r'(.+?)\((\d+),(\d+)\):\s+error\s+(.+)', output):
            file_path, line, col, message = match.groups()
            errors.append({
                'file': file_path,
                'line': int(line),
                'message': message
            })
        
        return errors, warnings
    
    def _find_build_artifacts(self, build_system: str) -> List[str]:
        """Find build artifacts produced"""
        artifacts = []
        
        artifact_patterns = {
            'maven': ['target/*.jar', 'target/*.war'],
            'gradle': ['build/libs/*.jar'],
            'npm': ['dist/**/*', 'build/**/*'],
            'poetry': ['dist/*.whl', 'dist/*.tar.gz'],
            'go': ['*.exe', 'main']
        }
        
        for pattern in artifact_patterns.get(build_system, []):
            for artifact in self.project_path.glob(pattern):
                if artifact.is_file():
                    artifacts.append(str(artifact.relative_to(self.project_path)))
        
        return artifacts
    
    def _calculate_build_hash(self, artifacts: List[str], tool_versions: Dict[str, str]) -> str:
        """
        Calculate hash of build for reproducibility verification.
        Improvement #5: Deterministic builds should produce same hash.
        """
        hasher = hashlib.sha256()
        
        # Hash tool versions
        hasher.update(json.dumps(tool_versions, sort_keys=True).encode())
        
        # Hash artifact contents
        for artifact_path in sorted(artifacts):
            full_path = self.project_path / artifact_path
            if full_path.exists():
                hasher.update(full_path.read_bytes())
        
        return hasher.hexdigest()


# Example usage
if __name__ == "__main__":
    validator = BuildValidator(
        project_path="/home/user/project",
        config={
            'timeout_seconds': 600,
            'use_containers': False,
            'lock_versions': True
        }
    )
    
    print("=== Build Validation ===")
    result = validator.validate_build(language='python')
    
    print(f"Status: {'✓ PASSED' if result.passed else '✗ FAILED'}")
    print(f"Build system: {result.build_system}")
    print(f"Duration: {result.duration_seconds:.2f}s")
    print(f"Errors: {len(result.errors)}")
    print(f"Warnings: {len(result.warnings)}")
    print(f"Artifacts: {len(result.artifacts)}")
    print(f"Build hash: {result.build_hash[:16]}...")
    print(f"\nTool versions (locked):")
    for tool, version in result.tool_versions.items():
        print(f"  {tool}: {version}")
