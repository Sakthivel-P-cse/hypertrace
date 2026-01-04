# Step 5: Fix Planner & Policy Engine

## Overview
The Fix Planner & Policy Engine selects appropriate code fixes from a library of safe, human-written templates and manages approval policies to ensure only safe, tested fixes are automatically applied.

## Architecture

### Components

1. **Fix Template Library** (`fix_templates.yaml`)
   - Library of safe, human-written code fix templates
   - Templates for common error types: NullPointerException, AttributeError, TimeoutException, etc.
   - Multi-language support: Java, Python, JavaScript, and generic templates
   - Each template includes: description, safety level, approval requirements, test requirements

2. **Fix Template Manager** (`fix_template_manager.py`)
   - Loads and manages fix templates
   - Finds matching templates for specific error types and languages
   - Renders templates with context variables
   - Validates template context

3. **Policy Engine** (`policy_engine.py`)
   - Manages fix approval policies
   - Enforces safety thresholds (high/medium/low)
   - Service-level policies (critical vs. non-critical)
   - Rate limiting and cooldown periods
   - Approval chain management

4. **Fix Planner** (`fix_planner.py`)
   - Main orchestrator integrating all components
   - Receives RCA results and code localization
   - Selects appropriate fix templates
   - Validates against policies
   - Generates fix plans for approval or execution

## Features

✅ **Safe Fix Templates**
- Human-written, tested code patterns
- Safety levels: high (auto-approve), medium (review), low (careful review)
- Language-specific and generic templates
- Parameterized for context injection

✅ **Policy-Based Approval**
- Service-level policies (critical services require review)
- Error-type policies (some errors need manual review)
- Confidence score thresholds
- Rate limiting to prevent fix storms

✅ **Template Matching**
- Automatic template selection based on error type and language
- Multiple fix options ranked by safety level
- Context-aware template rendering

✅ **Audit & Compliance**
- All fix decisions logged
- Approval chain tracking
- Policy validation and reporting

## Setup

### Install Dependencies

```bash
pip install pyyaml
```

### Configure Templates and Policies

Templates are defined in `fix_templates.yaml`. Customize for your needs:

```yaml
templates:
  - id: java-null-check
    name: "Add Null Check"
    language: java
    error_types:
      - NullPointerException
    safety_level: high
    fix_template: |
      if ({{variable}} != null) {
          {{original_line}}
      } else {
          logger.warn("Null {{variable}} encountered");
          return null;
      }
```

## Usage

### Basic Fix Planning

```python
from fix_planner import FixPlanner

# Initialize planner
planner = FixPlanner(
    templates_path="fix_templates.yaml",
    policy_config=None  # Uses defaults
)

# Incident with RCA and code location
incident = {
    'trace_id': 'trace-abc-123',
    'service': 'payment-service',
    'error_type': 'NullPointerException',
    'timestamp': '2026-01-01T10:00:00'
}

rca_result = {
    'probable_root_causes': [
        {'service': 'payment-service', 'confidence_score': 0.85}
    ]
}

code_location = {
    'root_cause_location': {
        'language': 'java',
        'file': 'PaymentService.java',
        'absolute_path': '/path/to/PaymentService.java',
        'line': 42,
        'method': 'processPayment',
        'exists': True,
        'code_context': {
            'lines': [
                {'line_number': 42, 'content': 'String email = customer.getEmail();', 'is_target': True}
            ]
        }
    }
}

# Plan fix
fix_plan = planner.plan_fix(incident, rca_result, code_location)

# Print report
print(planner.generate_fix_report(fix_plan))
```

### Template Management

```python
from fix_template_manager import FixTemplateManager

manager = FixTemplateManager("fix_templates.yaml")

# Find matching templates
templates = manager.find_matching_templates('NullPointerException', 'java')

for template in templates:
    print(f"{template['name']} - Safety: {template['safety_level']}")

# Render a template
template = manager.get_template_by_id('java-null-check')
context = {
    'variable': 'customer',
    'original_line': 'String email = customer.getEmail();'
}

rendered = manager.render_template(template, context)
print(rendered)
```

### Policy Enforcement

```python
from policy_engine import PolicyEngine

engine = PolicyEngine()

# Check if fix can be auto-applied
fix_request = {
    'service': 'api-gateway',
    'error_type': 'NullPointerException',
    'safety_level': 'high',
    'template_id': 'java-null-check',
    'confidence_score': 0.85,
    'file_path': 'src/Gateway.java'
}

decision = engine.can_auto_fix(fix_request)

print(f"Auto-fix approved: {decision['approved']}")
print(f"Reason: {decision['reason']}")
print(f"Requires review: {decision['requires_review']}")
```

## Example Output

```
================================================================================
FIX PLAN REPORT
================================================================================

Incident ID: trace-abc-123
Service:     api-gateway
Error Type:  NullPointerException
Status:      ready
Requires Approval: False

POLICY DECISION:
  Approved:        True
  Reason:          All policy checks passed
  Requires Review: False

PROPOSED FIXES (3 options):

1. Add Null Check (ID: java-null-check)
   Description:  Add null check before accessing object methods/properties
   Safety Level: high
   File:         /home/sakthi/PROJECTS/ccp/examples/Gateway.java
   Line:         42
   Function:     handleRequest

   Rendered Fix:
   if (user != null) {
       String name = user.getName();
   } else {
       // Handle null case
       logger.warn("Null user encountered");
       return null;  // or throw exception, or default value
   }

2. Add Error Logging (ID: java-add-logging)
   Description:  Add logging for better observability
   Safety Level: high
   ...

3. Wrap with Try-Catch (ID: java-try-catch-wrapper)
   Description:  Wrap risky operation in try-catch block
   Safety Level: medium
   ...

================================================================================
```

## Available Fix Templates

### Java Templates
- **java-null-check**: Add null checks before accessing objects
- **java-try-catch-wrapper**: Wrap code in try-catch blocks
- **java-resource-close**: Ensure proper resource closing with try-with-resources
- **java-add-logging**: Add error logging

### Python Templates
- **python-none-check**: Add None checks
- **python-try-except**: Wrap code in try-except blocks
- **python-dict-get**: Replace dict['key'] with dict.get('key', default)

### JavaScript Templates
- **js-null-undefined-check**: Add null/undefined checks
- **js-optional-chaining**: Use optional chaining (?.)
- **js-try-catch**: Wrap code in try-catch blocks

### Generic Templates
- **timeout-increase**: Increase operation timeout
- **retry-logic**: Add retry logic for transient failures
- **circuit-breaker**: Implement circuit breaker pattern

## Policy Configuration

### Safety Levels

```python
safety_thresholds = {
    'high': {
        'auto_approve': True,      # Can be auto-applied
        'require_review': False
    },
    'medium': {
        'auto_approve': False,     # Requires approval
        'require_review': True
    },
    'low': {
        'auto_approve': False,     # Requires careful review
        'require_review': True
    }
}
```

### Service Policies

```python
service_policies = {
    'critical_services': [
        'payment-service',
        'auth-service'
    ],  # Always require review
    'allow_auto_fix': [
        'api-gateway',
        'cache-service'
    ]  # Can auto-fix with high safety templates
}
```

### Rate Limits

```python
limits = {
    'max_auto_fixes_per_hour': 10,
    'max_auto_fixes_per_service': 3,
    'cooldown_minutes': 30
}
```

## Integration with Previous Steps

### Integration with RCA Engine (Step 3)

```python
from rca_engine import RCAEngine
from fix_planner import FixPlanner

# Run RCA
engine = RCAEngine(...)
rca_result = engine.analyze_incident(incident)

# Plan fix using RCA results
planner = FixPlanner()
fix_plan = planner.plan_fix(
    incident,
    rca_result,
    rca_result['code_location']  # From integrated code localizer
)
```

### Integration with Code Localizer (Step 4)

The Fix Planner uses code localization results to:
- Identify exact file and line for fix application
- Extract code context for template rendering
- Determine programming language
- Get function/method information

## Advanced Features

### Custom Templates

Add your own templates to `fix_templates.yaml`:

```yaml
- id: custom-timeout-fix
  name: "Custom Timeout Handler"
  language: java
  error_types:
    - TimeoutException
  description: "Add custom timeout handling"
  fix_template: |
    try {
        {{original_line}}
    } catch (TimeoutException e) {
        // Custom timeout handling
        logger.warn("Operation timed out, using fallback");
        return getFallbackValue();
    }
  safety_level: medium
  requires_review: true
  test_required: true
```

### Dynamic Policy Updates

```python
from policy_engine import PolicyEngine

engine = PolicyEngine()

# Update policies at runtime
engine.update_policy({
    'max_auto_fixes_per_hour': 20,
    'critical_services': ['payment-service', 'auth-service', 'data-service']
})
```

### Batch Fix Planning

```python
incidents = [
    {'incident_data': incident1, 'rca_result': rca1, 'code_location': loc1},
    {'incident_data': incident2, 'rca_result': rca2, 'code_location': loc2},
]

fix_plans = planner.batch_plan_fixes(incidents)

for plan in fix_plans:
    print(planner.generate_fix_report(plan))
```

## Testing

Run the test examples:

```bash
# Test template manager
python3 examples/fix_template_manager.py

# Test policy engine
python3 examples/policy_engine.py

# Test fix planner
python3 examples/fix_planner.py
```

## Safety Guidelines

### When to Auto-Fix
✅ High safety templates (null checks, logging)  
✅ Non-critical services  
✅ High RCA confidence score (>0.7)  
✅ Comprehensive test coverage exists  

### When to Require Review
⚠️ Medium/low safety templates  
⚠️ Critical services (payment, auth)  
⚠️ Architectural changes  
⚠️ Low RCA confidence  

### Never Auto-Fix
❌ Security-related errors  
❌ Memory/resource exhaustion  
❌ Database schema changes  
❌ Authentication/authorization issues  

## Troubleshooting

### No Templates Found
- Check error type spelling
- Verify language is supported
- Add custom template for specific error

### Policy Rejects Fix
- Check service is not in critical_services list
- Verify confidence score is above threshold
- Check rate limits haven't been exceeded

### Template Rendering Fails
- Ensure all required variables are in context
- Check template syntax in YAML file
- Validate context with `validate_template_context()`

## Next Steps

1. **Integrate with Patch Generator** (Step 6)
   - Use fix plans to generate actual code patches
   - Apply fixes to source files

2. **Add ML-Based Template Selection**
   - Train models on historical fix success rates
   - Improve template matching accuracy

3. **Enhance Template Library**
   - Add more language-specific templates
   - Include framework-specific fixes (Spring, Django, etc.)

4. **Implement A/B Testing**
   - Test different fix templates
   - Measure success rates

## Files Created

- `fix_templates.yaml` - Fix template library
- `fix_template_manager.py` - Template management and rendering
- `policy_engine.py` - Policy enforcement and approval
- `fix_planner.py` - Main fix planning orchestrator
- `README_Fix_Planner.md` - This documentation

## Integration Points

- **Step 3 (RCA Engine)**: Receives root cause analysis and confidence scores
- **Step 4 (Code Localizer)**: Uses exact code locations for fix application
- **Step 6 (Patch Generator)**: Provides fix plans for patch generation
- **Step 7 (Safety Gates)**: Fix plans specify test requirements
