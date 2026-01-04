# Contributing to CCP

Thank you for considering contributing to CCP! This document provides guidelines and instructions for contributing to the project.

---

## Table of Contents
- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Code Style](#code-style)
- [Submitting Changes](#submitting-changes)
- [Reporting Bugs](#reporting-bugs)
- [Suggesting Features](#suggesting-features)

---

## Code of Conduct

This project follows a code of conduct to foster an open and welcoming environment. By participating, you agree to:

- Be respectful and inclusive
- Accept constructive criticism gracefully
- Focus on what is best for the community
- Show empathy towards other community members

---

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/your-username/ccp.git
   cd ccp
   ```
3. **Add upstream remote:**
   ```bash
   git remote add upstream https://github.com/original-repo/ccp.git
   ```

---

## Development Setup

### Prerequisites
- Python 3.10+
- Neo4j 5.0+
- Redis 6.0+
- Prometheus
- Docker & Docker Compose

### Environment Setup

1. **Create a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # Development tools
   ```

3. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your local configuration
   ```

4. **Start infrastructure services:**
   ```bash
   cd docker
   docker-compose up -d
   ```

5. **Verify setup:**
   ```bash
   python3 examples/demo_end_to_end.py
   ```

---

## Making Changes

### Branching Strategy

- `main` - Stable production-ready code
- `develop` - Integration branch for features
- `feature/*` - New features
- `bugfix/*` - Bug fixes
- `hotfix/*` - Critical production fixes

### Workflow

1. **Sync with upstream:**
   ```bash
   git checkout main
   git pull upstream main
   ```

2. **Create a feature branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes** with clear, logical commits

4. **Keep your branch up to date:**
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

---

## Testing

### Running Tests

```bash
# All tests
pytest

# Specific test file
pytest tests/test_rca_engine.py

# With coverage
pytest --cov=examples tests/

# Verbose output
pytest -v
```

### Writing Tests

- Place test files in the `tests/` directory
- Name test files as `test_<module_name>.py`
- Use clear, descriptive test names: `test_should_detect_incident_when_error_rate_high()`
- Include docstrings explaining what each test validates
- Mock external dependencies (Neo4j, Redis, Prometheus)

Example test structure:
```python
import pytest
from examples.rca_engine import RCAEngine

class TestRCAEngine:
    """Tests for Root Cause Analysis Engine"""
    
    @pytest.fixture
    def mock_dependency_graph(self):
        """Fixture providing a mock dependency graph"""
        # Setup code
        yield mock_graph
        # Teardown code
    
    def test_should_identify_root_cause_with_high_confidence(self, mock_dependency_graph):
        """
        Given: An incident with clear error signals
        When: RCA engine analyzes the incident
        Then: Root cause is identified with >90% confidence
        """
        # Test implementation
```

### Test Coverage Requirements

- Minimum 80% code coverage for new features
- 100% coverage for critical paths (safety gates, deployments)
- Include edge cases and error scenarios
- Test both success and failure paths

---

## Code Style

### Python Standards

We follow [PEP 8](https://pep8.org/) with some modifications:

- **Line length:** 120 characters (not 79)
- **Docstrings:** Use Google-style docstrings
- **Type hints:** Required for function signatures
- **Imports:** Organized using `isort`

### Example:

```python
from typing import List, Dict, Optional
import logging

from examples.config_loader import load_config


def analyze_root_cause(
    incident_id: str,
    metrics: Dict[str, float],
    confidence_threshold: float = 0.8
) -> Optional[Dict[str, any]]:
    """
    Analyzes incident to identify root cause.
    
    Args:
        incident_id: Unique identifier for the incident
        metrics: Dictionary of metric names to values
        confidence_threshold: Minimum confidence score (0-1)
        
    Returns:
        Dictionary containing root cause analysis results, or None if
        confidence is below threshold
        
    Raises:
        ValueError: If incident_id is empty
        ConnectionError: If Neo4j connection fails
    """
    if not incident_id:
        raise ValueError("incident_id cannot be empty")
    
    # Implementation
```

### Linting

Run linters before committing:

```bash
# Auto-format code
black examples/*.py

# Sort imports
isort examples/*.py

# Check for issues
pylint examples/*.py
flake8 examples/*.py

# Type checking
mypy examples/*.py
```

### Pre-commit Hooks

We recommend using pre-commit hooks:

```bash
pip install pre-commit
pre-commit install
```

This automatically runs linters and formatters before each commit.

---

## Submitting Changes

### Pull Request Process

1. **Update documentation** for any changed functionality
2. **Add tests** for new features
3. **Ensure all tests pass:**
   ```bash
   pytest
   ```
4. **Run linters:**
   ```bash
   black examples/*.py
   flake8 examples/*.py
   ```
5. **Update CHANGELOG.md** with your changes
6. **Push to your fork:**
   ```bash
   git push origin feature/your-feature-name
   ```
7. **Create a Pull Request** on GitHub

### PR Template

Your PR description should include:

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] All existing tests pass
- [ ] New tests added for new features
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No new warnings generated
- [ ] Tests added/updated
- [ ] CHANGELOG.md updated
```

### Review Process

- At least one maintainer approval required
- All CI checks must pass
- Code must meet coverage requirements
- Changes must be properly documented

---

## Reporting Bugs

### Before Submitting

1. **Check existing issues** to avoid duplicates
2. **Test with latest version** to ensure bug still exists
3. **Gather debug information:**
   - Python version
   - OS and version
   - CCP version/commit
   - Steps to reproduce
   - Expected vs actual behavior
   - Error messages and stack traces

### Bug Report Template

```markdown
## Bug Description
Clear description of the bug

## Steps to Reproduce
1. Start service X
2. Run command Y
3. See error

## Expected Behavior
What should happen

## Actual Behavior
What actually happens

## Environment
- OS: Ubuntu 22.04
- Python: 3.10.12
- CCP Version: commit abc123
- Neo4j: 5.13.0
- Redis: 7.0.12

## Logs/Screenshots
Paste relevant logs or add screenshots

## Additional Context
Any other relevant information
```

---

## Suggesting Features

### Feature Request Template

```markdown
## Feature Description
Clear description of the proposed feature

## Use Case
Why is this feature needed? Who benefits?

## Proposed Solution
How would you implement this?

## Alternatives Considered
What other approaches did you consider?

## Additional Context
Any other relevant information, mockups, or examples
```

---

## Component-Specific Guidelines

### Adding a New Safety Gate

1. Create gate class in appropriate file
2. Implement required methods: `check()`, `get_gate_name()`
3. Add configuration in `safety_gate_config.yaml`
4. Update `safety_gate_orchestrator.py` to include new gate
5. Write comprehensive tests
6. Document gate in [README_Safety_Gates.md](README_Safety_Gates.md)

### Extending RCA Engine

1. Add new analysis method to `rca_engine.py`
2. Update confidence scoring in `confidence_scorer.py`
3. Add necessary data collection
4. Update tests
5. Document in [README_RCA.md](README_RCA.md)

### Adding Fix Templates

1. Add pattern to `fix_templates.yaml`
2. Include regex pattern, replacement, and confidence score
3. Test with various code samples
4. Document in [README_Fix_Planner.md](README_Fix_Planner.md)

---

## Documentation

### Documentation Standards

- Keep README.md up to date
- Use clear, concise language
- Include code examples
- Add diagrams where helpful (use Mermaid)
- Link related documents

### Updating Documentation

When making changes:
1. Update relevant README files
2. Update inline code comments
3. Update docstrings
4. Update CHANGELOG.md
5. Consider updating examples/

---

## Questions?

- Open a GitHub Discussion
- Tag maintainers in your PR
- Check existing documentation

---

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (MIT License).

---

Thank you for contributing to CCP! 🎉
