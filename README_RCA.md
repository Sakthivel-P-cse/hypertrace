# Step 3: Root Cause Analysis (RCA) Engine

## Overview
The RCA Engine analyzes incidents to identify probable root causes by:
- Building and querying service dependency graphs
- Analyzing error propagation through the system
- Correlating failures with recent code changes and deployments
- Calculating confidence scores for root cause candidates
- Generating comprehensive, actionable reports

## Architecture

### Components

1. **Dependency Graph Manager** (`dependency_graph.py`)
   - Uses Neo4j graph database for service topology
   - Tracks service dependencies and relationships
   - Annotates services with error information
   - Finds error propagation paths

2. **Git Analyzer** (`git_analyzer.py`)
   - Queries Git repository for recent commits
   - Correlates code changes with incidents
   - Identifies deployment events
   - Tracks file modification history

3. **Confidence Scorer** (`confidence_scorer.py`)
   - Calculates confidence scores for root cause candidates
   - Uses weighted scoring based on multiple factors:
     - Recent commits (30%)
     - Recent deployments (25%)
     - Error frequency (20%)
     - Error severity (15%)
     - Dependency proximity (10%)

4. **RCA Engine** (`rca_engine.py`)
   - Main orchestrator that integrates all components
   - Processes incident data
   - Builds and enriches candidate list
   - Generates comprehensive RCA reports

5. **RCA Visualizer** (`rca_visualizer.py`)
   - Formats reports in multiple formats (text, HTML, JSON)
   - Creates human-readable summaries
   - Generates visualizations

## Setup

### Prerequisites

1. **Install Neo4j**
   ```bash
   # Docker
   docker run -d \
     --name neo4j \
     -p 7474:7474 -p 7687:7687 \
     -e NEO4J_AUTH=neo4j/password \
     neo4j:latest
   ```

2. **Install Python Dependencies**
   ```bash
   pip install -r requirements_rca.txt
   ```

3. **Configure RCA Engine**
   - Edit `rca_config.yaml` with your settings
   - Update Neo4j connection details
   - Map service names to source code paths

### Initialize Service Dependency Graph

```python
from dependency_graph import DependencyGraphManager

# Connect to Neo4j
graph = DependencyGraphManager(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="password"
)

# Add services
graph.add_service("frontend", {"type": "web", "language": "javascript"})
graph.add_service("api-gateway", {"type": "api", "language": "python"})
graph.add_service("payment-service", {"type": "microservice", "language": "java"})
graph.add_service("db-service", {"type": "database"})

# Add dependencies
graph.add_dependency("frontend", "api-gateway")
graph.add_dependency("api-gateway", "payment-service")
graph.add_dependency("payment-service", "db-service")

graph.close()
```

## Usage

### Basic RCA Analysis

```python
from rca_engine import RCAEngine
from rca_visualizer import RCAVisualizer

# Initialize engine
engine = RCAEngine(
    neo4j_uri="bolt://localhost:7687",
    neo4j_user="neo4j",
    neo4j_password="password",
    repo_path="/path/to/your/repo"
)

# Define incident
incident = {
    "service": "payment-service",
    "endpoint": "/pay",
    "error_type": "NullPointerException",
    "error_message": "Cannot invoke method on null object",
    "timestamp": "2026-01-01T10:00:00",
    "severity": "high",
    "stack_trace": "at PaymentService.process(PaymentService.java:42)",
    "trace_id": "trace-abc-123"
}

# Perform RCA
report = engine.analyze_incident(incident)

# Visualize results
visualizer = RCAVisualizer()
print(visualizer.format_text_report(report))

# Save reports
visualizer.save_report(report, "rca_report.txt", format='text')
visualizer.save_report(report, "rca_report.html", format='html')
visualizer.save_report(report, "rca_report.json", format='json')

engine.close()
```

### Integration with Incident Processor

```python
# In your incident processing service
from rca_engine import RCAEngine

# Initialize RCA engine once
rca_engine = RCAEngine(...)

@app.route('/incident', methods=['POST'])
def receive_incident():
    incident = request.get_json(force=True)
    
    # Store incident (existing logic)
    store_incident(incident)
    
    # Perform RCA
    rca_report = rca_engine.analyze_incident(incident)
    
    # Log or forward the RCA report
    logging.info(f"RCA Report: {rca_report}")
    
    return jsonify({
        'status': 'analyzed',
        'rca_summary': rca_report['probable_root_causes'][:3]
    })
```

## Example Output

```
================================================================================
ROOT CAUSE ANALYSIS REPORT
================================================================================

INCIDENT SUMMARY
--------------------------------------------------------------------------------
Incident ID:       trace-abc-123
Timestamp:         2026-01-01T10:00:00
Affected Service:  payment-service
Error Type:        NullPointerException
Severity:          high
Analysis Time:     2026-01-01T10:05:00

PROBABLE ROOT CAUSES (Ranked by Confidence)
--------------------------------------------------------------------------------
╒════════╤═══════════════════╤═════════════╤══════════════╤════════════════════════╕
│   Rank │ Service           │ Endpoint    │   Confidence │ Recent Commit          │
╞════════╪═══════════════════╪═════════════╪══════════════╪════════════════════════╡
│      1 │ payment-service   │ /pay        │        0.850 │ abc12345 - Fix payment │
├────────┼───────────────────┼─────────────┼──────────────┼────────────────────────┤
│      2 │ db-service        │ /query      │        0.600 │ def45678 - Update quer │
╘════════╧═══════════════════╧═════════════╧══════════════╧════════════════════════╛

TOP CANDIDATE DETAILS
--------------------------------------------------------------------------------
Service:     payment-service
Endpoint:    /pay
Confidence:  0.850

Score Breakdown:
  recent_commit            : 0.900
  recent_deployment        : 0.000
  error_frequency          : 0.800
  error_severity           : 0.900
  dependency_proximity     : 1.000

Evidence:
  - [recent_commit] Commit abc12345 by john.doe
    Time: 2026-01-01 09:30:00
  - [error_frequency] 25 errors recorded
  - [direct_impact] Service directly affected by the error

RECOMMENDATIONS
--------------------------------------------------------------------------------
• Review recent commit abc12345: Fix payment validation logic
• High error frequency detected in payment-service - investigate immediately
• Check logs and traces for payment-service around incident time

================================================================================
```

## Advanced Features

### Batch Analysis
```python
incidents = [incident1, incident2, incident3]
reports = engine.batch_analyze(incidents)
```

### Custom Confidence Weights
```python
from confidence_scorer import ConfidenceScorer

scorer = ConfidenceScorer()
scorer.update_weights({
    "recent_commit": 0.4,
    "error_frequency": 0.3
})
```

### Dynamic Graph Updates
```python
# Update service metadata after deployment
graph.update_service_metadata("payment-service", {
    "last_deployment": "2026-01-01T09:45:00",
    "version": "v1.2.3",
    "commit_hash": "abc12345"
})
```

## Integration with OpenTelemetry

To enhance RCA with distributed tracing:

```python
# Parse OpenTelemetry spans to build dependency graph
from opentelemetry import trace

def build_graph_from_traces(traces):
    for trace in traces:
        for span in trace.spans:
            service = span.attributes.get('service.name')
            parent_service = span.parent.attributes.get('service.name')
            
            if parent_service:
                graph.add_dependency(service, parent_service)
```

## Troubleshooting

### Neo4j Connection Issues
```bash
# Check Neo4j is running
docker ps | grep neo4j

# Check logs
docker logs neo4j
```

### Git Repository Issues
```bash
# Verify repository
cd /path/to/repo && git status

# Check git log access
git log --since="24 hours ago"
```

## Next Steps

1. **Integrate with Incident Processor** (Step 2)
   - Auto-trigger RCA on incoming incidents
   - Store RCA reports alongside incidents

2. **Extend with Code Localizer** (Step 4)
   - Parse stack traces to identify exact files/functions
   - Map errors to source code locations

3. **Connect to Fix Planner** (Step 5)
   - Use RCA output to select appropriate fix templates
   - Automate remediation based on root cause

## Files Created

- `dependency_graph.py` - Service dependency graph manager
- `git_analyzer.py` - Git repository analyzer
- `confidence_scorer.py` - Root cause confidence scoring
- `rca_engine.py` - Main RCA orchestrator
- `rca_visualizer.py` - Report formatting and visualization
- `rca_config.yaml` - Configuration file
- `requirements_rca.txt` - Python dependencies
- `README_RCA.md` - This documentation
