# Root Cause Analysis Engine - Main orchestrator
# Integrates dependency graph, Git analysis, and confidence scoring
# Save as rca_engine.py

import logging
import json
from datetime import datetime
from pathlib import Path
from dependency_graph import DependencyGraphManager
from git_analyzer import GitAnalyzer
from confidence_scorer import ConfidenceScorer
from code_localizer import CodeLocalizer
from config_loader import load_config, get_env

logging.basicConfig(level=logging.INFO)

class RCAEngine:
    """
    Root Cause Analysis Engine
    Analyzes incidents to identify probable root causes
    """
    
    def __init__(self, neo4j_uri, neo4j_user, neo4j_password, repo_path):
        self.graph = DependencyGraphManager(neo4j_uri, neo4j_user, neo4j_password)
        self.git_analyzer = GitAnalyzer(repo_path)
        self.scorer = ConfidenceScorer()
        self.code_localizer = CodeLocalizer(repo_path)
        self.repo_path = repo_path
    
    def close(self):
        self.graph.close()
    
    def analyze_incident(self, incident_data):
        """
        Main RCA entry point
        
        incident_data = {
            "service": "payment-service",
            "endpoint": "/pay",
            "error_type": "NullPointerException",
            "error_message": "...",
            "timestamp": "2026-01-01T10:00:00",
            "severity": "high",
            "stack_trace": "...",
            "trace_id": "abc123"
        }
        """
        logging.info(f"Starting RCA for incident on {incident_data.get('service')}")
        
        # Step 1: Map incident to service in dependency graph
        affected_service = incident_data.get('service')
        if not affected_service:
            return {"error": "No service specified in incident"}
        
        # Step 2: Annotate the graph with error information
        self.graph.annotate_error(affected_service, {
            "error_type": incident_data.get('error_type'),
            "error_message": incident_data.get('error_message'),
            "timestamp": incident_data.get('timestamp'),
            "severity": incident_data.get('severity', 'medium')
        })
        
        # Step 3: Identify error propagation paths
        propagation_paths = self.graph.find_error_propagation_path(affected_service)
        logging.info(f"Found {len(propagation_paths)} error propagation paths")
        
        # Step 3.5: Code localization - map error to exact source code locations
        code_location = None
        if incident_data.get('stack_trace') or incident_data.get('logs'):
            code_location = self.code_localizer.localize_from_incident(incident_data)
            logging.info(f"Code localized to: {code_location.get('root_cause_location', {}).get('file', 'Unknown')}")
        
        # Step 4: Build candidate list (affected service + dependencies)
        candidates = self._build_candidate_list(
            affected_service,
            propagation_paths,
            incident_data
        )
        
        # Step 5: Enrich candidates with Git and deployment data
        enriched_candidates = self._enrich_candidates(candidates, incident_data)
        
        # Step 6: Calculate confidence scores and rank
        ranked_candidates = self.scorer.rank_candidates(enriched_candidates)
        
        # Step 7: Generate RCA report
        report = self._generate_rca_report(
            incident_data,
            ranked_candidates,
            propagation_paths,
            code_location
        )
        
        return report
    
    def _build_candidate_list(self, affected_service, propagation_paths, incident_data):
        """Build list of candidate services that could be root causes"""
        candidates = []
        seen_services = set()
        
        # Primary candidate: the affected service itself
        candidates.append({
            "service": affected_service,
            "endpoint": incident_data.get('endpoint', 'unknown'),
            "hops_from_error": 0,
            "error_count": 1,  # Will be updated from graph
            "error_severity": incident_data.get('severity', 'medium')
        })
        seen_services.add(affected_service)
        
        # Secondary candidates: services in dependency chain
        for path in propagation_paths:
            for i, service in enumerate(path):
                if service not in seen_services:
                    candidates.append({
                        "service": service,
                        "endpoint": "unknown",
                        "hops_from_error": i,
                        "error_count": 0,
                        "error_severity": "medium"
                    })
                    seen_services.add(service)
        
        # Get dependencies of affected service
        dependencies = self.graph.get_dependencies(affected_service)
        for dep in dependencies:
            dep_service = dep['service']
            if dep_service not in seen_services:
                candidates.append({
                    "service": dep_service,
                    "endpoint": "unknown",
                    "hops_from_error": 1,
                    "error_count": 0,
                    "error_severity": "medium"
                })
                seen_services.add(dep_service)
        
        return candidates
    
    def _enrich_candidates(self, candidates, incident_data):
        """Enrich candidates with Git and deployment information"""
        enriched = []
        
        for candidate in candidates:
            service_name = candidate['service']
            
            # Get service metadata from graph
            service_info = self.graph.get_service(service_name)
            
            # Get recent commits for this service
            # In production, map service name to source code path
            service_path = service_info.get('source_path') if service_info else None
            commits = self.git_analyzer.get_recent_commits(
                service_path=service_path,
                hours=48,
                limit=5
            )
            
            # Get deployment information
            deployments = self.git_analyzer.get_deployment_correlation(
                service_name,
                hours=24
            )
            
            # Update error count from graph metadata
            if service_info and 'error_count' in service_info:
                candidate['error_count'] = service_info['error_count']
            
            enriched.append({
                **candidate,
                "commits": commits,
                "deployments": deployments,
                "incident_time": incident_data.get('timestamp'),
                "service_metadata": service_info or {}
            })
        
        return enriched
    
    def _generate_rca_report(self, incident_data, ranked_candidates, propagation_paths, code_location=None):
        """Generate comprehensive RCA report"""
        # Top N candidates
        top_candidates = ranked_candidates[:5]
        
        # Build evidence for top candidate
        top_cause = top_candidates[0] if top_candidates else None
        evidence = []
        
        if top_cause:
            if top_cause.get('commits'):
                evidence.append(f"Recent commit: {top_cause['commits'][0]['hash'][:8]} - {top_cause['commits'][0]['message']}")
            
            if top_cause.get('deployments'):
                evidence.append(f"Recent deployment at {top_cause['deployments'][0]['date']}")
            
            if top_cause['error_count'] > 0:
                evidence.append(f"Error count: {top_cause['error_count']}")
            
            if top_cause.get('stack_trace'):
                evidence.append(f"Stack trace points to {top_cause['service']}")
        
        report = {
            "incident_id": incident_data.get('trace_id', 'unknown'),
            "incident_timestamp": incident_data.get('timestamp'),
            "affected_service": incident_data.get('service'),
            "error_type": incident_data.get('error_type'),
            "error_severity": incident_data.get('severity'),
            "analysis_timestamp": datetime.utcnow().isoformat(),
            "code_location": code_location,  # Add code localization results
            "probable_root_causes": [
                {
                    "rank": i + 1,
                    "service": c['service'],
                    "endpoint": c.get('endpoint', 'unknown'),
                    "confidence_score": c['confidence_score'],
                    "evidence": self._build_evidence(c),
                    "recent_commits": c.get('commits', [])[:2],
                    "recent_deployments": c.get('deployments', [])[:2],
                    "score_breakdown": c.get('score_breakdown', {})
                }
                for i, c in enumerate(top_candidates)
            ],
            "error_propagation_paths": propagation_paths[:3],
            "recommendation": self._generate_recommendation(top_cause, code_location)
        }
        
        return report
    
    def _build_evidence(self, candidate):
        """Build evidence list for a candidate"""
        evidence = []
        
        if candidate.get('commits'):
            commit = candidate['commits'][0]
            evidence.append({
                "type": "recent_commit",
                "description": f"Commit {commit['hash'][:8]} by {commit['author']}",
                "timestamp": commit['date']
            })
        
        if candidate.get('deployments'):
            deploy = candidate['deployments'][0]
            evidence.append({
                "type": "recent_deployment",
                "description": f"Deployment: {deploy['message']}",
                "timestamp": deploy['date']
            })
        
        if candidate['error_count'] > 0:
            evidence.append({
                "type": "error_frequency",
                "description": f"{candidate['error_count']} errors recorded",
                "timestamp": None
            })
        
        if candidate['hops_from_error'] == 0:
            evidence.append({
                "type": "direct_impact",
                "description": "Service directly affected by the error",
                "timestamp": None
            })
        
        return evidence
    
    def _generate_recommendation(self, top_cause, code_location=None):
        """Generate actionable recommendation"""
        if not top_cause:
            return "Insufficient data to generate recommendation"
        
        recommendations = []
        
        # Add code location recommendations first if available
        if code_location and code_location.get('recommendations'):
            recommendations.extend(code_location['recommendations'])
        
        if top_cause.get('commits'):
            commit = top_cause['commits'][0]
            recommendations.append(
                f"Review recent commit {commit['hash'][:8]}: {commit['message']}"
            )
        
        if top_cause.get('deployments'):
            recommendations.append(
                f"Consider rolling back deployment to {top_cause['service']}"
            )
        
        if top_cause['error_count'] > 10:
            recommendations.append(
                f"High error frequency detected in {top_cause['service']} - investigate immediately"
            )
        
        recommendations.append(
            f"Check logs and traces for {top_cause['service']} around incident time"
        )
        
        return " | ".join(recommendations)
    
    def batch_analyze(self, incidents):
        """Analyze multiple incidents"""
        reports = []
        for incident in incidents:
            try:
                report = self.analyze_incident(incident)
                reports.append(report)
            except Exception as e:
                logging.error(f"Failed to analyze incident: {e}")
                reports.append({"error": str(e), "incident": incident})
        
        return reports


# Example usage
if __name__ == "__main__":
    # Load configuration from YAML (with env var expansion)
    config_path = Path(__file__).parent / 'rca_config.yaml'
    config = load_config(str(config_path))
    
    # Initialize RCA Engine with config
    engine = RCAEngine(
        neo4j_uri=config['neo4j']['uri'],
        neo4j_user=config['neo4j']['user'],
        neo4j_password=config['neo4j']['password'],
        repo_path=config['git']['repo_path']
    )
    
    # Example incident
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
    
    # Print report
    print(json.dumps(report, indent=2))
    
    engine.close()
