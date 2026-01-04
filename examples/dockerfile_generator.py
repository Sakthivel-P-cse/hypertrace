#!/usr/bin/env python3
"""
Dockerfile Generator for Step 8: Deployment Automation

Generates Dockerfiles for various languages and frameworks.
Ensures immutable, reproducible container builds.
"""

import os
from pathlib import Path
from typing import Dict, Optional, List
from dataclasses import dataclass


@dataclass
class DockerfileConfig:
    """Configuration for Dockerfile generation"""
    language: str
    framework: Optional[str] = None
    base_image: Optional[str] = None
    app_dir: str = "/app"
    port: int = 8080
    build_commands: List[str] = None
    runtime_commands: List[str] = None
    environment_vars: Dict[str, str] = None
    health_check: Optional[str] = None


class DockerfileGenerator:
    """Generates production-ready Dockerfiles for different languages"""
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        
    def generate_dockerfile(self, config: DockerfileConfig) -> str:
        """Generate Dockerfile content based on configuration"""
        
        if config.language == 'python':
            return self._generate_python_dockerfile(config)
        elif config.language == 'java':
            return self._generate_java_dockerfile(config)
        elif config.language == 'javascript':
            return self._generate_javascript_dockerfile(config)
        elif config.language == 'go':
            return self._generate_go_dockerfile(config)
        else:
            return self._generate_generic_dockerfile(config)
    
    def _generate_python_dockerfile(self, config: DockerfileConfig) -> str:
        """Generate Python Dockerfile with best practices"""
        
        base_image = config.base_image or "python:3.11-slim"
        
        dockerfile = f"""# Generated Dockerfile for Python application
# Immutable deployment - tagged with commit hash
FROM {base_image}

# Set working directory
WORKDIR {config.app_dir}

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \\
    gcc \\
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first (layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \\
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \\
    chown -R appuser:appuser {config.app_dir}

USER appuser

# Expose port
EXPOSE {config.port}
"""
        
        # Add environment variables
        if config.environment_vars:
            for key, value in config.environment_vars.items():
                dockerfile += f"ENV {key}={value}\n"
        
        # Add health check
        if config.health_check:
            dockerfile += f"\nHEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \\\n"
            dockerfile += f"  CMD {config.health_check}\n"
        else:
            dockerfile += f"\nHEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \\\n"
            dockerfile += f"  CMD curl -f http://localhost:{config.port}/health || exit 1\n"
        
        # Add CMD
        if config.framework == 'flask':
            dockerfile += f"\nCMD [\"python\", \"-m\", \"flask\", \"run\", \"--host=0.0.0.0\", \"--port={config.port}\"]\n"
        elif config.framework == 'fastapi':
            dockerfile += f"\nCMD [\"uvicorn\", \"main:app\", \"--host\", \"0.0.0.0\", \"--port\", \"{config.port}\"]\n"
        else:
            dockerfile += f"\nCMD [\"python\", \"main.py\"]\n"
        
        return dockerfile
    
    def _generate_java_dockerfile(self, config: DockerfileConfig) -> str:
        """Generate Java Dockerfile with multi-stage build"""
        
        base_image = config.base_image or "openjdk:17-slim"
        
        dockerfile = f"""# Generated Dockerfile for Java application
# Multi-stage build for minimal image size
FROM maven:3.8-openjdk-17 AS builder

WORKDIR /build

# Copy pom.xml first (layer caching)
COPY pom.xml .

# Download dependencies
RUN mvn dependency:go-offline

# Copy source code
COPY src ./src

# Build application
RUN mvn clean package -DskipTests

# Runtime stage
FROM {base_image}

WORKDIR {config.app_dir}

# Copy JAR from builder stage
COPY --from=builder /build/target/*.jar app.jar

# Create non-root user
RUN useradd -m -u 1000 appuser
USER appuser

# Expose port
EXPOSE {config.port}
"""
        
        # Add environment variables
        if config.environment_vars:
            for key, value in config.environment_vars.items():
                dockerfile += f"ENV {key}={value}\n"
        
        # Add health check
        if config.health_check:
            dockerfile += f"\nHEALTHCHECK --interval=30s --timeout=3s --start-period=60s --retries=3 \\\n"
            dockerfile += f"  CMD {config.health_check}\n"
        else:
            dockerfile += f"\nHEALTHCHECK --interval=30s --timeout=3s --start-period=60s --retries=3 \\\n"
            dockerfile += f"  CMD curl -f http://localhost:{config.port}/actuator/health || exit 1\n"
        
        # Add CMD
        dockerfile += f"\nCMD [\"java\", \"-jar\", \"app.jar\"]\n"
        
        return dockerfile
    
    def _generate_javascript_dockerfile(self, config: DockerfileConfig) -> str:
        """Generate Node.js Dockerfile with best practices"""
        
        base_image = config.base_image or "node:18-alpine"
        
        dockerfile = f"""# Generated Dockerfile for Node.js application
FROM {base_image}

WORKDIR {config.app_dir}

# Copy package files first (layer caching)
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production && npm cache clean --force

# Copy application code
COPY . .

# Create non-root user
RUN addgroup -g 1000 appuser && \\
    adduser -D -u 1000 -G appuser appuser && \\
    chown -R appuser:appuser {config.app_dir}

USER appuser

# Expose port
EXPOSE {config.port}
"""
        
        # Add environment variables
        if config.environment_vars:
            for key, value in config.environment_vars.items():
                dockerfile += f"ENV {key}={value}\n"
        
        # Add health check
        if config.health_check:
            dockerfile += f"\nHEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \\\n"
            dockerfile += f"  CMD {config.health_check}\n"
        else:
            dockerfile += f"\nHEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \\\n"
            dockerfile += f"  CMD wget --no-verbose --tries=1 --spider http://localhost:{config.port}/health || exit 1\n"
        
        # Add CMD
        dockerfile += f"\nCMD [\"node\", \"server.js\"]\n"
        
        return dockerfile
    
    def _generate_go_dockerfile(self, config: DockerfileConfig) -> str:
        """Generate Go Dockerfile with multi-stage build"""
        
        dockerfile = f"""# Generated Dockerfile for Go application
# Multi-stage build for minimal image
FROM golang:1.21-alpine AS builder

WORKDIR /build

# Copy go mod files first (layer caching)
COPY go.mod go.sum ./

# Download dependencies
RUN go mod download

# Copy source code
COPY . .

# Build application
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o app .

# Runtime stage - minimal image
FROM alpine:latest

WORKDIR {config.app_dir}

# Install ca-certificates for HTTPS
RUN apk --no-cache add ca-certificates

# Copy binary from builder
COPY --from=builder /build/app .

# Create non-root user
RUN addgroup -g 1000 appuser && \\
    adduser -D -u 1000 -G appuser appuser && \\
    chown -R appuser:appuser {config.app_dir}

USER appuser

# Expose port
EXPOSE {config.port}
"""
        
        # Add environment variables
        if config.environment_vars:
            for key, value in config.environment_vars.items():
                dockerfile += f"ENV {key}={value}\n"
        
        # Add health check
        if config.health_check:
            dockerfile += f"\nHEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \\\n"
            dockerfile += f"  CMD {config.health_check}\n"
        else:
            dockerfile += f"\nHEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \\\n"
            dockerfile += f"  CMD wget --no-verbose --tries=1 --spider http://localhost:{config.port}/health || exit 1\n"
        
        # Add CMD
        dockerfile += f"\nCMD [\"./app\"]\n"
        
        return dockerfile
    
    def _generate_generic_dockerfile(self, config: DockerfileConfig) -> str:
        """Generate generic Dockerfile"""
        
        base_image = config.base_image or "ubuntu:22.04"
        
        dockerfile = f"""# Generated Dockerfile
FROM {base_image}

WORKDIR {config.app_dir}

# Copy application code
COPY . .
"""
        
        # Add custom build commands
        if config.build_commands:
            dockerfile += "\n# Build commands\n"
            for cmd in config.build_commands:
                dockerfile += f"RUN {cmd}\n"
        
        # Expose port
        dockerfile += f"\nEXPOSE {config.port}\n"
        
        # Add environment variables
        if config.environment_vars:
            for key, value in config.environment_vars.items():
                dockerfile += f"ENV {key}={value}\n"
        
        # Add CMD
        if config.runtime_commands:
            dockerfile += f"\nCMD {config.runtime_commands}\n"
        
        return dockerfile
    
    def save_dockerfile(self, content: str, output_path: Optional[str] = None) -> str:
        """Save Dockerfile to disk"""
        
        if output_path is None:
            output_path = self.project_path / "Dockerfile"
        else:
            output_path = Path(output_path)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            f.write(content)
        
        print(f"✓ Dockerfile generated: {output_path}")
        return str(output_path)
    
    def generate_dockerignore(self) -> str:
        """Generate .dockerignore file"""
        
        dockerignore = """# Git
.git
.gitignore

# IDE
.vscode
.idea
*.swp
*.swo

# Python
__pycache__
*.pyc
*.pyo
*.pyd
.Python
*.egg-info
dist
build
*.egg
.pytest_cache
.coverage

# Node.js
node_modules
npm-debug.log

# Java
target/
*.class
*.jar
*.war

# Logs
*.log
logs/

# Tests
tests/
test/
*.test.js

# Documentation
docs/
*.md
!README.md

# CI/CD
.github
.gitlab-ci.yml
Jenkinsfile

# Environment
.env
.env.local
*.local

# OS
.DS_Store
Thumbs.db
"""
        
        dockerignore_path = self.project_path / ".dockerignore"
        with open(dockerignore_path, 'w') as f:
            f.write(dockerignore)
        
        print(f"✓ .dockerignore generated: {dockerignore_path}")
        return str(dockerignore_path)


# Example usage
if __name__ == "__main__":
    # Example: Generate Python Flask Dockerfile
    generator = DockerfileGenerator("/path/to/project")
    
    config = DockerfileConfig(
        language='python',
        framework='flask',
        port=8080,
        environment_vars={
            'FLASK_APP': 'app.py',
            'FLASK_ENV': 'production'
        }
    )
    
    dockerfile_content = generator.generate_dockerfile(config)
    print(dockerfile_content)
    
    # Save to disk
    # generator.save_dockerfile(dockerfile_content)
    # generator.generate_dockerignore()
