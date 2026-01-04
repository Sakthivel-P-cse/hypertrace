# Step 6: Patch Generator

## Overview

The Patch Generator is a sophisticated code patching system that generates, validates, and applies code fixes automatically. It integrates with the Fix Planner (Step 5) to receive fix plans, generates minimal and explainable code patches, validates them for safety, and applies them to the codebase with full Git integration.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              PATCH GENERATOR (Step 6)                   │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────┐ │
│  │ Patch        │───▶│ Patch        │───▶│ Patch    │ │
│  │ Generator    │    │ Validator    │    │ Applier  │ │
│  └──────────────┘    └──────────────┘    └──────────┘ │
│         │                    │                  │       │
│         ▼                    ▼                  ▼       │
│   Generate Patches    Validate Safety    Apply + Commit│
│   from Templates      & Correctness      to Git Repo   │
│                                                          │
└─────────────────────────────────────────────────────────┘
              ▲                                  │
              │                                  │
      ┌───────┴────────┐              ┌─────────▼─────────┐
      │  Fix Planner   │              │   Git Commits     │
      │   (Step 5)     │              │   + Rollback      │
      └────────────────┘              └───────────────────┘
```

## Components

### 1. **patch_generator.py** - Main Orchestrator

The central component that coordinates the entire patching workflow.

**Key Features:**
- Receives fix plans from Fix Planner
- Generates code patches by applying templates
- Orchestrates validation and application
- Provides end-to-end patch generation
- Supports dry-run mode for safety
- Generates comprehensive reports

**Main Class: `PatchGenerator`**

```python
generator = PatchGenerator(
    repo_path="/path/to/repo",
    fix_planner=fix_planner,
    config={
        'validation_level': 'normal',  # strict, normal, permissive
        'auto_commit': True,
        'create_backups': True,
        'dry_run': False
    }
)

# Generate patches from incident
result = generator.generate_patches_from_incident(
    incident_data=incident_data,
    rca_result=rca_result,
    code_location=code_location,
    dry_run=False
)

print(generator.generate_report(result))
```

### 2. **patch_validator.py** - Safety & Correctness Validation

Validates code patches before application to ensure safety and correctness.

**Validation Checks:**
- ✅ **Syntax Validation**: Ensures code is syntactically correct
- ✅ **Import Consistency**: Checks import statements aren't broken
- ✅ **Function Signatures**: Validates signatures are preserved
- ✅ **Dangerous Patterns**: Detects unsafe code patterns
- ✅ **File Size Limits**: Prevents oversized files
- ✅ **Complexity Metrics**: Checks code complexity
- ✅ **Language-Specific**: Python, Java, JavaScript support

**Validation Levels:**
- `STRICT`: All checks must pass (no warnings allowed)
- `NORMAL`: Critical checks must pass (warnings allowed)
- `PERMISSIVE`: Only syntax checks (maximum flexibility)

**Main Class: `PatchValidator`**

```python
validator = PatchValidator({
    'validation_level': 'normal',
    'max_file_size': 1024 * 1024,  # 1MB
    'max_lines_changed': 500,
    'max_complexity_increase': 10
})

is_valid, issues = validator.validate_patch(
    original_content=original_code,
    patched_content=patched_code,
    file_path="service.py",
    language="python"
)

print(validator.format_validation_report(issues))
```

**Dangerous Patterns Detected:**
- `eval()` and `exec()` usage
- Dynamic imports with `__import__()`
- Shell injection risks (`subprocess.call(..., shell=True)`)
- Command injection (`os.system()`)
- Unsafe deserialization (`pickle.loads()`)
- Unsafe YAML loading (`yaml.load()` without `safe_load`)

### 3. **patch_applier.py** - Git-Integrated Patch Application

Applies validated patches to files with full Git integration and rollback support.

**Key Features:**
- Applies patches to source files
- Automatic Git commits with meaningful messages
- Unified diff generation (Git-style)
- Backup creation before applying changes
- Batch patch application
- Rollback support (revert commits)
- Dry-run mode for testing

**Main Class: `PatchApplier`**

```python
applier = PatchApplier(
    repo_path="/path/to/repo",
    config={
        'auto_commit': True,
        'create_backups': True
    }
)

# Apply single patch
result = applier.apply_patch(
    file_path="service.py",
    original_content=original_code,
    patched_content=patched_code,
    dry_run=False,
    commit_message="Fix: Add timeout to HTTP requests"
)

print(f"Success: {result.success}")
print(f"Commit: {result.commit_hash}")
print(f"Lines added: {result.lines_added}")
print(f"Lines removed: {result.lines_removed}")
print("\nDiff:\n", result.diff)

# Rollback if needed
if not tests_passed:
    applier.rollback(result.commit_hash)
```

## Workflow

### End-to-End Patch Generation Process

```
1. Receive Fix Plan
   └─▶ From Fix Planner (Step 5)
       Contains: templates, target files, context

2. Generate Patches
   └─▶ Apply templates to code
       Generate: original → patched content
       Output: List of patches

3. Validate Patches
   └─▶ Check syntax, safety, correctness
       Detect: dangerous patterns
       Filter: Only valid patches proceed

4. Apply Patches
   └─▶ Write to files
       Create: Git commits
       Backup: Original files
       Generate: Unified diffs

5. Report Results
   └─▶ Success/failure status
       Commit hashes
       Validation issues
       Performance metrics
```

### Data Flow

```python
# Input: Fix Plan from Fix Planner
fix_plan = {
    'incident_id': 'INC-001',
    'fixes': [
        {
            'fix_id': 'FIX-001',
            'template_id': 'retry-logic',
            'target_file': 'service.py',
            'target_location': {
                'line_number': 42,
                'function': 'fetch_data'
            },
            'template': 'retry logic code...',
            'language': 'python',
            'description': 'Add retry logic'
        }
    ],
    'requires_approval': False
}

# Output: Patch Generation Result
result = {
    'success': True,
    'incident_id': 'INC-001',
    'patches_generated': 1,
    'patches_applied': 1,
    'patches_failed': 0,
    'commit_hashes': ['abc123...'],
    'patch_results': [
        {
            'file_path': 'service.py',
            'success': True,
            'lines_added': 5,
            'lines_removed': 1,
            'diff': '--- a/service.py\n+++ b/service.py\n...'
        }
    ],
    'duration_seconds': 2.34
}
```

## Configuration

### Patch Generator Config

```python
config = {
    # Validation strictness
    'validation_level': 'normal',  # strict, normal, permissive
    
    # Safety limits
    'max_lines_changed': 500,
    'max_file_size': 1024 * 1024,  # 1MB
    
    # Git integration
    'auto_commit': True,
    'create_backups': True,
    
    # Testing mode
    'dry_run': False  # True = don't actually modify files
}
```

### Validation Configuration

```python
validation_config = {
    'validation_level': 'normal',
    'max_file_size': 1024 * 1024,
    'max_lines_changed': 500,
    'max_complexity_increase': 10
}
```

## Usage Examples

### Example 1: Basic Patch Generation

```python
from patch_generator import PatchGenerator
from fix_planner import FixPlanner
from fix_template_manager import FixTemplateManager
from policy_engine import PolicyEngine

# Setup
template_mgr = FixTemplateManager("fix_templates.yaml")
policy_engine = PolicyEngine(policy_config)
fix_planner = FixPlanner(template_mgr, policy_engine)

generator = PatchGenerator(
    repo_path="/path/to/repo",
    fix_planner=fix_planner,
    config={'dry_run': False}
)

# Generate patches from incident
result = generator.generate_patches_from_incident(
    incident_data={
        'incident_id': 'INC-001',
        'service': 'api-service',
        'error_type': 'TimeoutError'
    },
    rca_result={
        'root_causes': [{
            'service': 'api-service',
            'confidence_score': 0.95
        }]
    },
    code_location={
        'primary_location': {
            'file': 'service.py',
            'line_number': 42,
            'function': 'fetch_data'
        }
    }
)

print(generator.generate_report(result))
```

### Example 2: Dry Run Mode (Safe Testing)

```python
# Test patch generation without modifying files
result = generator.generate_patches_from_plan(
    fix_plan=fix_plan,
    dry_run=True  # No files modified
)

if result.success and result.patches_applied > 0:
    print("All patches valid! Safe to apply.")
    # Now apply for real
    result_real = generator.generate_patches_from_plan(
        fix_plan=fix_plan,
        dry_run=False
    )
```

### Example 3: Validation Only

```python
from patch_validator import PatchValidator

validator = PatchValidator({'validation_level': 'strict'})

original = open('service.py').read()
patched = apply_my_changes(original)

is_valid, issues = validator.validate_patch(
    original, patched, 'service.py', 'python'
)

if is_valid:
    print("✓ Patch is safe to apply")
else:
    print("✗ Validation failed:")
    print(validator.format_validation_report(issues))
```

### Example 4: Manual Patch Application

```python
from patch_applier import PatchApplier

applier = PatchApplier("/path/to/repo")

result = applier.apply_patch(
    file_path="service.py",
    original_content=original,
    patched_content=patched,
    dry_run=False,
    commit_message="Fix: Add timeout handling"
)

if result.success:
    print(f"✓ Patch applied: {result.commit_hash}")
    print(f"  +{result.lines_added} -{result.lines_removed} lines")
else:
    print(f"✗ Failed: {result.error}")
```

### Example 5: Rollback on Failure

```python
# Apply patches
result = generator.generate_patches_from_incident(...)

if result.success:
    # Run tests
    tests_passed = run_tests()
    
    if not tests_passed:
        # Rollback all commits
        print("Tests failed, rolling back...")
        generator.rollback_patches(result.commit_hashes)
```

### Example 6: Batch Patch Application

```python
patches = [
    {
        'file_path': 'service1.py',
        'original': original1,
        'patched': patched1
    },
    {
        'file_path': 'service2.py',
        'original': original2,
        'patched': patched2
    }
]

results = applier.apply_batch(
    patches,
    dry_run=False,
    commit_message="Auto-fix: Multiple services"
)

for result in results:
    print(f"{result.file_path}: {'✓' if result.success else '✗'}")
```

## Integration with Previous Steps

### Step 5 (Fix Planner) → Step 6 (Patch Generator)

```python
# Step 5: Get fix plan
fix_plan = fix_planner.plan_fix(
    incident_data,
    rca_result,
    code_location
)

# Step 6: Generate and apply patches
result = patch_generator.generate_patches_from_plan(fix_plan)

# Or use the convenience method:
result = patch_generator.generate_patches_from_incident(
    incident_data,
    rca_result,
    code_location
)
```

## Output Format

### Patch Generation Result

```python
{
    'success': bool,
    'incident_id': str,
    'patches_generated': int,
    'patches_applied': int,
    'patches_failed': int,
    'validation_issues': [
        {
            'fix_id': str,
            'level': 'pass|warning|fail',
            'check': str,
            'message': str,
            'line_number': int
        }
    ],
    'patch_results': [
        {
            'file_path': str,
            'success': bool,
            'lines_added': int,
            'lines_removed': int,
            'commit_hash': str,
            'diff': str,  # Unified diff format
            'error': str
        }
    ],
    'commit_hashes': [str],
    'duration_seconds': float,
    'error': str
}
```

### Unified Diff Format

```diff
--- a/service.py
+++ b/service.py
@@ -40,7 +40,12 @@
 def fetch_data(url):
-    response = requests.get(url)
+    max_retries = 3
+    for attempt in range(max_retries):
+        try:
+            response = requests.get(url, timeout=10)
+            break
+        except requests.Timeout:
+            if attempt == max_retries - 1:
+                raise
     return response.json()
```

## Safety Features

### 1. Validation Before Application
- All patches validated before touching files
- Syntax errors caught early
- Dangerous patterns detected

### 2. Backup System
- Original files backed up automatically
- Stored in `.patch_backups/` directory
- Timestamped for easy recovery

### 3. Git Integration
- Every change committed to Git
- Meaningful commit messages
- Easy rollback with commit hashes

### 4. Dry Run Mode
- Test patches without modifying files
- Validate entire workflow safely
- Preview diffs before application

### 5. Atomic Operations
- Each patch is atomic (all-or-nothing)
- Failed patches don't affect others
- Batch operations stop on first failure

## Error Handling

```python
try:
    result = generator.generate_patches_from_incident(
        incident_data,
        rca_result,
        code_location
    )
    
    if not result.success:
        print(f"Patch generation failed: {result.error}")
        print(f"Applied: {result.patches_applied}")
        print(f"Failed: {result.patches_failed}")
        
        # Review validation issues
        for issue in result.validation_issues:
            print(f"- {issue['check']}: {issue['message']}")
        
        # Review patch failures
        for patch in result.patch_results:
            if not patch['success']:
                print(f"Failed: {patch['file_path']}")
                print(f"Error: {patch['error']}")
    else:
        print("All patches applied successfully!")
        print(f"Commits: {result.commit_hashes}")
        
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Performance Considerations

- **Parallel Validation**: Patches can be validated in parallel
- **Incremental Application**: Patches applied one at a time
- **Efficient Diffing**: Uses Python's `difflib` for fast diffs
- **Lazy File Reading**: Files read only when needed

## Limitations & Future Improvements

### Current Limitations
1. Simple string-based template application
2. Limited AST manipulation
3. No cross-file refactoring support
4. Single repository only

### Planned Improvements
1. **AST-Based Patching**: Use AST manipulation for precise code changes
2. **Multi-Repository**: Support patches across multiple repositories
3. **Parallel Application**: Apply independent patches in parallel
4. **Conflict Resolution**: Automatic merge conflict resolution
5. **Semantic Validation**: Deep semantic analysis of patches
6. **Test Integration**: Automatic test execution after patching

## Testing

Run the example code in each module:

```bash
# Test patch validator
python examples/patch_validator.py

# Test patch applier
python examples/patch_applier.py

# Test patch generator
python examples/patch_generator.py
```

## Dependencies

```
# Python standard library
- ast
- difflib
- pathlib
- subprocess
- tempfile

# Step 5 dependencies (Fix Planner)
- fix_planner
- fix_template_manager
- policy_engine
```

## Next Steps

After implementing the Patch Generator (Step 6), proceed to:

- **Step 7**: Safety Gates - Automated testing and validation before deployment
- **Step 8**: Deployment Automation - Build, containerize, and deploy fixed services
- **Step 9**: Verification Loop - Monitor metrics and rollback if fix doesn't work

## Summary

The Patch Generator (Step 6) completes the "fix generation" phase of the self-healing system. It takes fix plans from Step 5 and converts them into actual code changes, with comprehensive validation and Git integration. The system ensures safety through multiple validation layers, provides full rollback capabilities, and generates explainable diffs for every change.

**Key Achievements:**
- ✅ Template-based patch generation
- ✅ Multi-language validation (Python, Java, JavaScript)
- ✅ Dangerous pattern detection
- ✅ Git commit integration
- ✅ Unified diff generation
- ✅ Rollback support
- ✅ Dry-run mode
- ✅ Comprehensive reporting
