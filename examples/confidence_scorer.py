# Confidence Scorer - Assigns confidence scores to root cause candidates
# Save as confidence_scorer.py

import logging
from datetime import datetime, timedelta
import json

logging.basicConfig(level=logging.INFO)

class ConfidenceScorer:
    """
    Calculates confidence scores for root cause candidates based on:
    - Proximity to recent code changes/deployments
    - Error frequency and severity
    - Historical incident data
    - Error propagation patterns
    """
    
    def __init__(self):
        self.weights = {
            "recent_commit": 0.3,
            "recent_deployment": 0.25,
            "error_frequency": 0.2,
            "error_severity": 0.15,
            "dependency_proximity": 0.1
        }
    
    def calculate_time_decay_score(self, timestamp_str, decay_hours=24):
        """
        Calculate score based on how recent an event is
        Returns score between 0 and 1, with 1 being most recent
        """
        try:
            event_time = datetime.fromisoformat(timestamp_str.replace(' ', 'T'))
            now = datetime.now()
            hours_ago = (now - event_time).total_seconds() / 3600
            
            if hours_ago < 0:
                return 1.0
            
            # Exponential decay
            score = max(0, 1 - (hours_ago / decay_hours))
            return score
        except Exception as e:
            logging.warning(f"Error parsing timestamp {timestamp_str}: {e}")
            return 0.0
    
    def score_recent_commit(self, commits, incident_time=None):
        """Score based on recent commits"""
        if not commits:
            return 0.0
        
        # Most recent commit gets highest score
        most_recent = commits[0]
        commit_time = most_recent.get('date', '')
        
        if incident_time:
            # Check if commit is before the incident
            try:
                commit_dt = datetime.fromisoformat(commit_time.replace(' ', 'T'))
                incident_dt = datetime.fromisoformat(incident_time.replace(' ', 'T'))
                
                if commit_dt > incident_dt:
                    # Commit after incident, less likely to be the cause
                    return 0.1
            except:
                pass
        
        return self.calculate_time_decay_score(commit_time, decay_hours=48)
    
    def score_recent_deployment(self, deployments, incident_time=None):
        """Score based on recent deployments"""
        if not deployments:
            return 0.0
        
        most_recent = deployments[0]
        deploy_time = most_recent.get('date', '')
        
        return self.calculate_time_decay_score(deploy_time, decay_hours=24)
    
    def score_error_frequency(self, error_count, max_count=100):
        """Score based on error frequency (more errors = higher score)"""
        if error_count <= 0:
            return 0.0
        
        # Normalize to 0-1 range
        return min(1.0, error_count / max_count)
    
    def score_error_severity(self, severity):
        """Score based on error severity"""
        severity_map = {
            "critical": 1.0,
            "high": 0.8,
            "medium": 0.5,
            "low": 0.2,
            "info": 0.1
        }
        
        return severity_map.get(severity.lower(), 0.5)
    
    def score_dependency_proximity(self, hops_from_error):
        """
        Score based on proximity in dependency graph
        0 hops = directly affected service (score = 1.0)
        More hops = lower score
        """
        if hops_from_error <= 0:
            return 1.0
        
        # Exponential decay with hops
        return max(0, 1 - (hops_from_error * 0.3))
    
    def calculate_composite_score(self, candidate):
        """
        Calculate composite confidence score for a root cause candidate
        
        candidate = {
            "service": "payment-service",
            "commits": [...],
            "deployments": [...],
            "error_count": 15,
            "error_severity": "high",
            "hops_from_error": 1,
            "incident_time": "2026-01-01 10:00:00"
        }
        """
        scores = {}
        
        # Calculate individual scores
        scores['recent_commit'] = self.score_recent_commit(
            candidate.get('commits', []),
            candidate.get('incident_time')
        )
        
        scores['recent_deployment'] = self.score_recent_deployment(
            candidate.get('deployments', []),
            candidate.get('incident_time')
        )
        
        scores['error_frequency'] = self.score_error_frequency(
            candidate.get('error_count', 0)
        )
        
        scores['error_severity'] = self.score_error_severity(
            candidate.get('error_severity', 'medium')
        )
        
        scores['dependency_proximity'] = self.score_dependency_proximity(
            candidate.get('hops_from_error', 99)
        )
        
        # Calculate weighted sum
        composite_score = sum(
            scores[key] * self.weights[key]
            for key in scores.keys()
        )
        
        return {
            "composite_score": round(composite_score, 3),
            "component_scores": scores,
            "weights": self.weights
        }
    
    def rank_candidates(self, candidates):
        """
        Rank a list of root cause candidates by confidence score
        Returns sorted list with scores
        """
        scored_candidates = []
        
        for candidate in candidates:
            score_result = self.calculate_composite_score(candidate)
            scored_candidates.append({
                **candidate,
                "confidence_score": score_result["composite_score"],
                "score_breakdown": score_result["component_scores"]
            })
        
        # Sort by confidence score (descending)
        scored_candidates.sort(key=lambda x: x["confidence_score"], reverse=True)
        
        return scored_candidates
    
    def update_weights(self, new_weights):
        """Update scoring weights (for tuning)"""
        self.weights.update(new_weights)
        logging.info(f"Updated weights: {self.weights}")


# Example usage and testing
if __name__ == "__main__":
    scorer = ConfidenceScorer()
    
    # Example candidates
    candidates = [
        {
            "service": "payment-service",
            "endpoint": "/pay",
            "commits": [{"date": "2026-01-01 09:30:00", "hash": "abc123"}],
            "deployments": [{"date": "2026-01-01 09:45:00"}],
            "error_count": 25,
            "error_severity": "high",
            "hops_from_error": 0,
            "incident_time": "2026-01-01 10:00:00"
        },
        {
            "service": "db-service",
            "endpoint": "/query",
            "commits": [{"date": "2025-12-30 14:00:00", "hash": "def456"}],
            "deployments": [{"date": "2025-12-30 15:00:00"}],
            "error_count": 5,
            "error_severity": "medium",
            "hops_from_error": 1,
            "incident_time": "2026-01-01 10:00:00"
        },
        {
            "service": "auth-service",
            "endpoint": "/validate",
            "commits": [],
            "deployments": [],
            "error_count": 2,
            "error_severity": "low",
            "hops_from_error": 2,
            "incident_time": "2026-01-01 10:00:00"
        }
    ]
    
    # Rank candidates
    ranked = scorer.rank_candidates(candidates)
    
    print("\nRoot Cause Candidates (Ranked):")
    print("=" * 80)
    for i, candidate in enumerate(ranked, 1):
        print(f"{i}. {candidate['service']} - {candidate['endpoint']}")
        print(f"   Confidence: {candidate['confidence_score']:.3f}")
        print(f"   Breakdown: {candidate['score_breakdown']}")
        print(f"   Errors: {candidate['error_count']}, Severity: {candidate['error_severity']}")
        print()
