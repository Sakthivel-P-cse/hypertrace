# Step 4: Code Localizer

## Overview
The Code Localizer maps incidents to exact source files, functions, and line numbers by parsing stack traces, analyzing logs, and correlating errors with actual source code in your repository.

## Architecture

### Components

1. **Stack Trace Parser** (`stack_trace_parser.py`)
   - Multi-language support: Java, Python, JavaScript, Go, C#, Ruby
   - Extracts file paths, line numbers, function/method names
   - Auto-detects language from stack trace format
   - Identifies root cause location (first frame)

2. **Log Parser** (`log_parser.py`)
   - Extracts error entries from application logs
   - Parses log levels, timestamps, logger names, and messages
   - Groups errors by type and frequency
   - Filters errors by service and time range

3. **Source Code Mapper** (`source_code_mapper.py`)
   - Builds index of all source files in repository
   - Locates files using package/namespace information
   - Extracts code context around error locations
   - Identifies function definitions
   - Scans for common error-prone patterns

4. **Code Localizer** (`code_localizer.py`)
   - Main orchestrator integrating all components
   - Maps incidents to exact code locations
   - Generates actionable recommendations
   - Produces comprehensive localization reports

## Features

✅ **Multi-Language Stack Trace Parsing**
- Java (with package, class, method)
- Python (with file, line, function)
- JavaScript/Node.js (with file, line, column)
- Go, C#, Ruby support

✅ **Intelligent Source Code Mapping**
- Fast file indexing and lookup
- Package/namespace-aware file resolution
- Code context extraction (surrounding lines)
- Function definition extraction

✅ **Log Analysis**
- Error extraction and classification
- Frequency analysis
- Exception name extraction
- Service-specific filtering

✅ **Error Pattern Detection**
- NullPointerException patterns
- Empty catch blocks
- Resource leaks
- TODO/FIXME markers

## Setup

### Install Dependencies

```bash
pip install pathlib
# No additional dependencies required - uses Python stdlib
```

### Initialize Code Localizer

```python
from code_localizer import CodeLocalizer

# Initialize with your repository path
localizer = CodeLocalizer(
    repo_path="/path/to/your/repo",
    source_roots=['src', 'app', 'services']  # Optional
)
```

## Usage

### Basic Code Localization

```python
from code_localizer import CodeLocalizer

localizer = CodeLocalizer("/home/sakthi/PROJECTS/ccp")

# Incident with stack trace
incident = {
    "trace_id": "trace-abc-123",
    "service": "payment-service",
    "error_type": "NullPointerException",
    "error_message": "Cannot invoke method on null object",
    "language": "java",
    "stack_trace": """
java.lang.NullPointerException: Cannot invoke method on null object
    at com.example.payment.PaymentService.processPayment(PaymentService.java:42)
    at com.example.payment.PaymentController.handleRequest(PaymentController.java:128)
    """,
    "logs": """
2026-01-01 10:00:16 [payment-service] ERROR: NullPointerException in PaymentService.processPayment
    """
}

# Localize code
result = localizer.localize_from_incident(incident)

# Print report
print(localizer.generate_report(result))
```

### Stack Trace Parsing Only

```python
from stack_trace_parser import StackTraceParser

parser = StackTraceParser()

# Parse Java stack trace
java_trace = """
java.lang.NullPointerException: Cannot invoke method on null object
    at com.example.payment.PaymentService.processPayment(PaymentService.java:42)
    at com.example.web.RequestHandler.dispatch(RequestHandler.java:89)
"""

frames = parser.parse(java_trace)

for frame in frames:
    print(f"File: {frame['file']}")
    print(f"Line: {frame['line']}")
    print(f"Class: {frame['full_class']}")
    print(f"Method: {frame['method']}")
    print()

# Get root cause (first frame)
root_cause = parser.extract_root_cause(frames)
print(f"Root cause: {parser.format_frame(root_cause)}")
```

### Log Analysis

```python
from log_parser import LogParser

parser = LogParser()

logs = """
2026-01-01 10:00:15 [payment-service] INFO: Processing payment
2026-01-01 10:00:16 [payment-service] ERROR: NullPointerException occurred
2026-01-01 10:00:17 [db-service] ERROR: Connection timeout
"""

# Parse all errors
errors = parser.parse_logs(logs)

# Group by error type
frequency = parser.get_error_frequency(errors)
print(frequency)

# Find errors for specific service
service_errors = parser.find_errors_by_service(logs, "payment-service")
```

### Source Code Mapping

```python
from source_code_mapper import SourceCodeMapper

mapper = SourceCodeMapper("/path/to/repo")

# Locate a file
file_path = mapper.locate_file("PaymentService.java", package="com.example.payment")

# Get code context
if file_path:
    context = mapper.get_code_context(str(file_path), line_number=42, context_lines=5)
    
    for line in context['lines']:
        marker = ">>>" if line['is_target'] else "   "
        print(f"{marker} {line['line_number']:4d}: {line['content']}")

# Extract function definition
func_def = mapper.extract_function_definition(
    str(file_path),
    function_name="processPayment",
    language="java"
)

# Find error-prone patterns
issues = mapper.find_error_prone_patterns(str(file_path))
for issue in issues:
    print(f"Line {issue['line']}: {issue['issue']}")
```

## Integration with RCA Engine

The Code Localizer is now integrated with the RCA Engine:

```python
from rca_engine import RCAEngine

engine = RCAEngine(
    neo4j_uri="bolt://localhost:7687",
    neo4j_user="neo4j",
    neo4j_password="password",
    repo_path="/path/to/repo"
)

# Incident with stack trace
incident = {
    "service": "payment-service",
    "endpoint": "/pay",
    "error_type": "NullPointerException",
    "timestamp": "2026-01-01T10:00:00",
    "severity": "high",
    "stack_trace": "...",
    "logs": "...",
    "trace_id": "trace-abc-123"
}

# RCA now includes code localization
report = engine.analyze_incident(incident)

# Access code location
code_location = report['code_location']
if code_location:
    root_cause = code_location['root_cause_location']
    print(f"Error located at: {root_cause['file']}:{root_cause['line']}")
    print(f"In function: {root_cause.get('function')}")
```

## Example Output

```
================================================================================
CODE LOCALIZATION REPORT
================================================================================

Incident ID: trace-abc-123
Service:     payment-service
Error Type:  NullPointerException

ROOT CAUSE LOCATION:
  PaymentService.java:42 in processPayment()

  Code Context:
      38: public class PaymentService {
      39:     
      40:     public void processPayment(PaymentRequest request) {
      41:         Customer customer = request.getCustomer();
  >>> 42:         String email = customer.getEmail();  // NullPointerException here
      43:         // Send payment notification
      44:         notificationService.send(email, "Payment processed");
      45:     }
      46: }

STACK TRACE LOCATIONS:
  1. PaymentService.java:42 in processPayment()
  2. PaymentController.java:128 in handleRequest()
  3. RequestHandler.java:89 in dispatch()

ERROR ANALYSIS:
  Total errors:       3
  Unique error types: 2

  Error frequency:
    NullPointerException: 2
    Unknown: 1

RECOMMENDATIONS:
  • Review code at PaymentService.java:42 in function 'processPayment'
  • Add null checks before accessing object methods/properties
  • Check logs and traces for payment-service around incident time

================================================================================
```

## Language-Specific Examples

### Java
```java
// Stack trace format
at com.example.payment.PaymentService.processPayment(PaymentService.java:42)

// Parsed result
{
  "language": "java",
  "package": "com.example.payment",
  "class": "PaymentService",
  "method": "processPayment",
  "file": "PaymentService.java",
  "line": 42
}
```

### Python
```python
# Stack trace format
File "/app/payment_service.py", line 42, in process_payment

# Parsed result
{
  "language": "python",
  "file": "/app/payment_service.py",
  "line": 42,
  "function": "process_payment"
}
```

### JavaScript
```javascript
// Stack trace format
at PaymentService.processPayment (/app/services/payment.js:42:15)

// Parsed result
{
  "language": "javascript",
  "function": "PaymentService.processPayment",
  "file": "/app/services/payment.js",
  "line": 42,
  "column": 15
}
```

## Error Pattern Detection

The Code Localizer can identify common error-prone patterns:

```python
# Potential NullPointerException
result.getCustomer().getEmail()

# Empty catch block
catch (Exception e) { }

# System.exit() call
System.exit(1);

# TODO comments
// TODO: Add null check here
```

## Advanced Features

### Batch Processing

```python
incidents = [incident1, incident2, incident3]
results = localizer.localize_batch(incidents)

for result in results:
    print(localizer.generate_report(result))
```

### Custom Source Roots

```python
# For monorepo or custom structure
localizer = CodeLocalizer(
    repo_path="/path/to/repo",
    source_roots=['backend/src', 'frontend/src', 'shared/lib']
)
```

### Function Definition Extraction

```python
# Extract full function signature and location
func_def = mapper.extract_function_definition(
    file_path="PaymentService.java",
    function_name="processPayment",
    language="java"
)

print(f"Function: {func_def['function']}")
print(f"Location: {func_def['file']}:{func_def['line_number']}")
print(f"Definition: {func_def['definition']}")
```

## Testing

Run the test examples:

```bash
# Test stack trace parser
python3 examples/stack_trace_parser.py

# Test log parser
python3 examples/log_parser.py

# Test source code mapper
python3 examples/source_code_mapper.py

# Test code localizer
python3 examples/code_localizer.py
```

## Troubleshooting

### File Not Found
- Ensure `repo_path` points to the correct repository root
- Check that source files are indexed (not in ignored directories)
- Verify package/namespace matches directory structure

### Stack Trace Not Parsed
- Check language detection or specify language explicitly
- Verify stack trace format matches expected patterns
- Use generic parser for unknown formats

### Missing Code Context
- Ensure file exists and is readable
- Check line number is within file bounds
- Verify file encoding (UTF-8 expected)

## Next Steps

1. **Integrate with Fix Planner** (Step 5)
   - Use code locations to identify where fixes should be applied
   - Map error types to fix templates

2. **Enhance with AST Parsing**
   - Use language-specific parsers (e.g., javalang, ast for Python)
   - Extract more detailed code structure

3. **Add Machine Learning**
   - Train models on historical incidents
   - Improve root cause prediction

4. **Extend Pattern Detection**
   - Add more error-prone patterns
   - Custom pattern configuration

## Files Created

- `stack_trace_parser.py` - Multi-language stack trace parser
- `log_parser.py` - Application log analyzer
- `source_code_mapper.py` - Source code file mapper and analyzer
- `code_localizer.py` - Main code localizer orchestrator
- `README_Code_Localizer.md` - This documentation

## Integration Points

- **Step 2 (Incident Processor)**: Receives incidents with stack traces and logs
- **Step 3 (RCA Engine)**: Provides exact code locations for root cause analysis
- **Step 5 (Fix Planner)**: Supplies precise locations for applying fixes
- **Step 6 (Patch Generator)**: Uses file paths and line numbers for patch generation
