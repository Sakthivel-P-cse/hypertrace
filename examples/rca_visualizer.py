# RCA Report Formatter and Visualizer
# Generates human-readable reports and visualizations
# Save as rca_visualizer.py

import json
from datetime import datetime
from tabulate import tabulate
import logging

logging.basicConfig(level=logging.INFO)

class RCAVisualizer:
    """Generate human-readable RCA reports and visualizations"""
    
    def format_text_report(self, rca_report):
        """Generate a text-based RCA report"""
        lines = []
        lines.append("=" * 80)
        lines.append("ROOT CAUSE ANALYSIS REPORT")
        lines.append("=" * 80)
        lines.append("")
        
        # Incident Summary
        lines.append("INCIDENT SUMMARY")
        lines.append("-" * 80)
        lines.append(f"Incident ID:       {rca_report.get('incident_id', 'N/A')}")
        lines.append(f"Timestamp:         {rca_report.get('incident_timestamp', 'N/A')}")
        lines.append(f"Affected Service:  {rca_report.get('affected_service', 'N/A')}")
        lines.append(f"Error Type:        {rca_report.get('error_type', 'N/A')}")
        lines.append(f"Severity:          {rca_report.get('error_severity', 'N/A')}")
        lines.append(f"Analysis Time:     {rca_report.get('analysis_timestamp', 'N/A')}")
        lines.append("")
        
        # Probable Root Causes
        lines.append("PROBABLE ROOT CAUSES (Ranked by Confidence)")
        lines.append("-" * 80)
        
        causes = rca_report.get('probable_root_causes', [])
        if causes:
            table_data = []
            for cause in causes:
                commits_info = ""
                if cause.get('recent_commits'):
                    commit = cause['recent_commits'][0]
                    commits_info = f"{commit['hash'][:8]} - {commit['message'][:40]}"
                
                table_data.append([
                    cause['rank'],
                    cause['service'],
                    cause['endpoint'],
                    f"{cause['confidence_score']:.3f}",
                    commits_info
                ])
            
            lines.append(tabulate(
                table_data,
                headers=['Rank', 'Service', 'Endpoint', 'Confidence', 'Recent Commit'],
                tablefmt='grid'
            ))
        else:
            lines.append("No root causes identified")
        
        lines.append("")
        
        # Top Candidate Details
        if causes:
            top_cause = causes[0]
            lines.append("TOP CANDIDATE DETAILS")
            lines.append("-" * 80)
            lines.append(f"Service:     {top_cause['service']}")
            lines.append(f"Endpoint:    {top_cause['endpoint']}")
            lines.append(f"Confidence:  {top_cause['confidence_score']:.3f}")
            lines.append("")
            lines.append("Score Breakdown:")
            breakdown = top_cause.get('score_breakdown', {})
            for key, value in breakdown.items():
                lines.append(f"  {key:25s}: {value:.3f}")
            lines.append("")
            
            # Evidence
            lines.append("Evidence:")
            for evidence in top_cause.get('evidence', []):
                lines.append(f"  - [{evidence['type']}] {evidence['description']}")
                if evidence.get('timestamp'):
                    lines.append(f"    Time: {evidence['timestamp']}")
            lines.append("")
        
        # Error Propagation Paths
        paths = rca_report.get('error_propagation_paths', [])
        if paths:
            lines.append("ERROR PROPAGATION PATHS")
            lines.append("-" * 80)
            for i, path in enumerate(paths, 1):
                lines.append(f"{i}. {' -> '.join(path)}")
            lines.append("")
        
        # Recommendations
        lines.append("RECOMMENDATIONS")
        lines.append("-" * 80)
        recommendation = rca_report.get('recommendation', 'No recommendations available')
        for rec in recommendation.split('|'):
            lines.append(f"• {rec.strip()}")
        lines.append("")
        
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def format_html_report(self, rca_report):
        """Generate an HTML RCA report"""
        html = []
        html.append("<!DOCTYPE html>")
        html.append("<html><head>")
        html.append("<title>RCA Report</title>")
        html.append("<style>")
        html.append("body { font-family: Arial, sans-serif; margin: 20px; }")
        html.append("h1 { color: #333; }")
        html.append("h2 { color: #555; border-bottom: 2px solid #ddd; padding-bottom: 5px; }")
        html.append("table { border-collapse: collapse; width: 100%; margin: 20px 0; }")
        html.append("th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }")
        html.append("th { background-color: #4CAF50; color: white; }")
        html.append("tr:nth-child(even) { background-color: #f2f2f2; }")
        html.append(".high { color: red; font-weight: bold; }")
        html.append(".medium { color: orange; font-weight: bold; }")
        html.append(".low { color: green; font-weight: bold; }")
        html.append(".evidence { background-color: #f9f9f9; padding: 10px; margin: 10px 0; border-left: 4px solid #4CAF50; }")
        html.append("</style>")
        html.append("</head><body>")
        
        html.append("<h1>Root Cause Analysis Report</h1>")
        
        # Incident Summary
        html.append("<h2>Incident Summary</h2>")
        html.append("<table>")
        html.append(f"<tr><th>Incident ID</th><td>{rca_report.get('incident_id', 'N/A')}</td></tr>")
        html.append(f"<tr><th>Timestamp</th><td>{rca_report.get('incident_timestamp', 'N/A')}</td></tr>")
        html.append(f"<tr><th>Affected Service</th><td>{rca_report.get('affected_service', 'N/A')}</td></tr>")
        html.append(f"<tr><th>Error Type</th><td>{rca_report.get('error_type', 'N/A')}</td></tr>")
        
        severity = rca_report.get('error_severity', 'medium')
        html.append(f"<tr><th>Severity</th><td class='{severity}'>{severity.upper()}</td></tr>")
        html.append(f"<tr><th>Analysis Time</th><td>{rca_report.get('analysis_timestamp', 'N/A')}</td></tr>")
        html.append("</table>")
        
        # Probable Root Causes
        html.append("<h2>Probable Root Causes</h2>")
        causes = rca_report.get('probable_root_causes', [])
        if causes:
            html.append("<table>")
            html.append("<tr><th>Rank</th><th>Service</th><th>Endpoint</th><th>Confidence</th><th>Recent Commit</th></tr>")
            for cause in causes:
                commits_info = "None"
                if cause.get('recent_commits'):
                    commit = cause['recent_commits'][0]
                    commits_info = f"{commit['hash'][:8]} - {commit['message'][:50]}"
                
                html.append(f"<tr>")
                html.append(f"<td>{cause['rank']}</td>")
                html.append(f"<td><strong>{cause['service']}</strong></td>")
                html.append(f"<td>{cause['endpoint']}</td>")
                html.append(f"<td>{cause['confidence_score']:.3f}</td>")
                html.append(f"<td>{commits_info}</td>")
                html.append(f"</tr>")
            html.append("</table>")
        
        # Top Candidate Evidence
        if causes:
            top_cause = causes[0]
            html.append("<h2>Top Candidate Evidence</h2>")
            html.append(f"<p><strong>Service:</strong> {top_cause['service']}</p>")
            html.append(f"<p><strong>Confidence Score:</strong> {top_cause['confidence_score']:.3f}</p>")
            
            html.append("<div class='evidence'>")
            html.append("<h3>Evidence:</h3>")
            html.append("<ul>")
            for evidence in top_cause.get('evidence', []):
                html.append(f"<li><strong>[{evidence['type']}]</strong> {evidence['description']}")
                if evidence.get('timestamp'):
                    html.append(f" <em>(at {evidence['timestamp']})</em>")
                html.append("</li>")
            html.append("</ul>")
            html.append("</div>")
        
        # Recommendations
        html.append("<h2>Recommendations</h2>")
        recommendation = rca_report.get('recommendation', 'No recommendations available')
        html.append("<ul>")
        for rec in recommendation.split('|'):
            html.append(f"<li>{rec.strip()}</li>")
        html.append("</ul>")
        
        html.append("</body></html>")
        
        return "\n".join(html)
    
    def format_json_report(self, rca_report):
        """Format RCA report as pretty-printed JSON"""
        return json.dumps(rca_report, indent=2)
    
    def save_report(self, rca_report, output_path, format='text'):
        """Save RCA report to file"""
        if format == 'text':
            content = self.format_text_report(rca_report)
        elif format == 'html':
            content = self.format_html_report(rca_report)
        elif format == 'json':
            content = self.format_json_report(rca_report)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        with open(output_path, 'w') as f:
            f.write(content)
        
        logging.info(f"Saved RCA report to {output_path}")


# Example usage
if __name__ == "__main__":
    visualizer = RCAVisualizer()
    
    # Example RCA report
    example_report = {
        "incident_id": "trace-abc-123",
        "incident_timestamp": "2026-01-01T10:00:00",
        "affected_service": "payment-service",
        "error_type": "NullPointerException",
        "error_severity": "high",
        "analysis_timestamp": "2026-01-01T10:05:00",
        "probable_root_causes": [
            {
                "rank": 1,
                "service": "payment-service",
                "endpoint": "/pay",
                "confidence_score": 0.85,
                "evidence": [
                    {
                        "type": "recent_commit",
                        "description": "Commit abc12345 by john.doe",
                        "timestamp": "2026-01-01T09:30:00"
                    },
                    {
                        "type": "error_frequency",
                        "description": "25 errors recorded",
                        "timestamp": None
                    }
                ],
                "recent_commits": [
                    {
                        "hash": "abc12345",
                        "author": "john.doe",
                        "date": "2026-01-01 09:30:00",
                        "message": "Fix payment validation logic"
                    }
                ],
                "recent_deployments": [],
                "score_breakdown": {
                    "recent_commit": 0.9,
                    "recent_deployment": 0.0,
                    "error_frequency": 0.8,
                    "error_severity": 0.9,
                    "dependency_proximity": 1.0
                }
            }
        ],
        "error_propagation_paths": [
            ["payment-service", "api-gateway", "frontend"]
        ],
        "recommendation": "Review recent commit abc12345 | Check logs for payment-service around incident time"
    }
    
    # Generate text report
    print(visualizer.format_text_report(example_report))
    
    # Save reports
    # visualizer.save_report(example_report, "rca_report.txt", format='text')
    # visualizer.save_report(example_report, "rca_report.html", format='html')
    # visualizer.save_report(example_report, "rca_report.json", format='json')
