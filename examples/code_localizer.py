# Code Localizer - Main module integrating all components
# Maps incidents to exact source files and functions
# Save as code_localizer.py

import logging
from typing import Dict, List, Optional
from stack_trace_parser import StackTraceParser
from log_parser import LogParser
from source_code_mapper import SourceCodeMapper

logging.basicConfig(level=logging.INFO)

class CodeLocalizer:
    """
    Main code localizer that integrates stack trace parsing,
    log analysis, and source code mapping to identify exact
    code locations related to incidents
    """
    
    def __init__(self, repo_path: str, source_roots: Optional[List[str]] = None):
        """
        Initialize code localizer
        
        Args:
            repo_path: Path to the source code repository
            source_roots: List of source directories (e.g., ['src', 'app'])
        """
        self.repo_path = repo_path
        self.stack_parser = StackTraceParser()
        self.log_parser = LogParser()
        self.source_mapper = SourceCodeMapper(repo_path, source_roots)
    
    def localize_from_incident(self, incident_data: Dict) -> Dict:
        """
        Main entry point: localize code from incident data
        
        Args:
            incident_data: Incident dict containing:
                - stack_trace (optional): stack trace string
                - logs (optional): log content
                - error_type: type of error
                - service: affected service
        
        Returns:
            Localization result with:
                - locations: list of code locations
                - root_cause_location: most likely root cause
                - error_summary: parsed error information
        """
        result = {
            'incident_id': incident_data.get('trace_id', 'unknown'),
            'service': incident_data.get('service'),
            'error_type': incident_data.get('error_type'),
            'locations': [],
            'root_cause_location': None,
            'error_summary': {},
            'recommendations': []
        }
        
        # Parse stack trace if available
        if incident_data.get('stack_trace'):
            stack_locations = self._localize_from_stack_trace(
                incident_data['stack_trace'],
                incident_data.get('language')
            )
            result['locations'].extend(stack_locations)
            
            # First location is typically the root cause
            if stack_locations:
                result['root_cause_location'] = stack_locations[0]
        
        # Parse logs if available
        if incident_data.get('logs'):
            log_analysis = self._analyze_logs(
                incident_data['logs'],
                incident_data.get('service')
            )
            result['error_summary'] = log_analysis
        
        # Extract error message
        if incident_data.get('error_message'):
            result['error_summary']['error_message'] = incident_data['error_message']
        
        # Generate recommendations
        result['recommendations'] = self._generate_recommendations(result)
        
        return result
    
    def _localize_from_stack_trace(self, stack_trace: str, language: Optional[str] = None) -> List[Dict]:
        """Parse stack trace and map to source code locations"""
        # Parse stack trace
        frames = self.stack_parser.parse(stack_trace, language)
        
        if not frames:
            logging.warning("No stack frames found in stack trace")
            return []
        
        locations = []
        
        for frame in frames:
            # Map frame to source file
            mapped_frame = self.source_mapper.map_stack_frame(frame)
            
            # Get code context if file exists
            if mapped_frame.get('exists') and mapped_frame.get('absolute_path'):
                context = self.source_mapper.get_code_context(
                    mapped_frame['absolute_path'],
                    mapped_frame.get('line', 1),
                    context_lines=5
                )
                
                if context:
                    mapped_frame['code_context'] = context
                
                # Try to extract function definition
                function_name = mapped_frame.get('method') or mapped_frame.get('function')
                if function_name:
                    func_def = self.source_mapper.extract_function_definition(
                        mapped_frame['absolute_path'],
                        function_name,
                        mapped_frame.get('language', 'java')
                    )
                    if func_def:
                        mapped_frame['function_definition'] = func_def
            
            locations.append(mapped_frame)
        
        return locations
    
    def _analyze_logs(self, logs: str, service_name: Optional[str] = None) -> Dict:
        """Analyze logs to extract error information"""
        # Parse all errors from logs
        errors = self.log_parser.parse_logs(logs)
        
        # Filter by service if specified
        if service_name:
            errors = self.log_parser.find_errors_by_service(logs, service_name)
        
        # Group by error type
        error_frequency = self.log_parser.get_error_frequency(errors)
        
        # Extract most recent/relevant error
        recent_error = errors[0] if errors else None
        
        return {
            'total_errors': len(errors),
            'error_frequency': error_frequency,
            'recent_error': recent_error,
            'unique_error_types': len(error_frequency)
        }
    
    def _generate_recommendations(self, localization_result: Dict) -> List[str]:
        """Generate actionable recommendations based on localization"""
        recommendations = []
        
        root_cause = localization_result.get('root_cause_location')
        
        if root_cause:
            if root_cause.get('exists'):
                file_path = root_cause.get('relative_path', root_cause.get('absolute_path'))
                line = root_cause.get('line', 'unknown')
                function = root_cause.get('method') or root_cause.get('function', 'unknown')
                
                recommendations.append(
                    f"Review code at {file_path}:{line} in function '{function}'"
                )
                
                # Check for common error patterns
                if root_cause.get('absolute_path'):
                    issues = self.source_mapper.find_error_prone_patterns(
                        root_cause['absolute_path']
                    )
                    if issues:
                        recommendations.append(
                            f"Found {len(issues)} potential code issues in {file_path}"
                        )
            else:
                recommendations.append(
                    f"Source file '{root_cause.get('file')}' not found in repository - may be from external dependency"
                )
        
        # Recommendations based on error type
        error_type = localization_result.get('error_type', '')
        
        if 'NullPointer' in error_type:
            recommendations.append("Add null checks before accessing object methods/properties")
        elif 'Connection' in error_type or 'Timeout' in error_type:
            recommendations.append("Check network connectivity and service availability")
        elif 'Memory' in error_type:
            recommendations.append("Investigate memory usage and potential memory leaks")
        
        # Recommendations based on error frequency
        error_summary = localization_result.get('error_summary', {})
        if error_summary.get('total_errors', 0) > 10:
            recommendations.append("High error frequency detected - this may indicate a systemic issue")
        
        return recommendations
    
    def localize_batch(self, incidents: List[Dict]) -> List[Dict]:
        """Process multiple incidents"""
        results = []
        
        for incident in incidents:
            try:
                result = self.localize_from_incident(incident)
                results.append(result)
            except Exception as e:
                logging.error(f"Failed to localize incident: {e}")
                results.append({
                    'error': str(e),
                    'incident': incident
                })
        
        return results
    
    def format_location(self, location: Dict) -> str:
        """Format a code location as a readable string"""
        parts = []
        
        if location.get('relative_path'):
            parts.append(location['relative_path'])
        elif location.get('file'):
            parts.append(location['file'])
        
        if location.get('line'):
            parts.append(f"line {location['line']}")
        
        func = location.get('method') or location.get('function')
        if func:
            parts.append(f"in {func}()")
        
        return ' '.join(parts) if parts else 'Unknown location'
    
    def generate_report(self, localization_result: Dict) -> str:
        """Generate a human-readable localization report"""
        lines = []
        lines.append("=" * 80)
        lines.append("CODE LOCALIZATION REPORT")
        lines.append("=" * 80)
        lines.append("")
        
        # Incident info
        lines.append(f"Incident ID: {localization_result.get('incident_id', 'N/A')}")
        lines.append(f"Service:     {localization_result.get('service', 'N/A')}")
        lines.append(f"Error Type:  {localization_result.get('error_type', 'N/A')}")
        lines.append("")
        
        # Root cause location
        root_cause = localization_result.get('root_cause_location')
        if root_cause:
            lines.append("ROOT CAUSE LOCATION:")
            lines.append(f"  {self.format_location(root_cause)}")
            
            if root_cause.get('code_context'):
                lines.append("\n  Code Context:")
                for line_info in root_cause['code_context']['lines']:
                    marker = ">>>" if line_info['is_target'] else "   "
                    lines.append(f"  {marker} {line_info['line_number']:4d}: {line_info['content']}")
            lines.append("")
        
        # All locations
        locations = localization_result.get('locations', [])
        if len(locations) > 1:
            lines.append("STACK TRACE LOCATIONS:")
            for i, loc in enumerate(locations[:5], 1):  # Top 5
                lines.append(f"  {i}. {self.format_location(loc)}")
            lines.append("")
        
        # Error summary
        error_summary = localization_result.get('error_summary', {})
        if error_summary:
            lines.append("ERROR ANALYSIS:")
            lines.append(f"  Total errors:       {error_summary.get('total_errors', 0)}")
            lines.append(f"  Unique error types: {error_summary.get('unique_error_types', 0)}")
            
            freq = error_summary.get('error_frequency', {})
            if freq:
                lines.append("\n  Error frequency:")
                for error_type, count in list(freq.items())[:5]:
                    lines.append(f"    {error_type}: {count}")
            lines.append("")
        
        # Recommendations
        recommendations = localization_result.get('recommendations', [])
        if recommendations:
            lines.append("RECOMMENDATIONS:")
            for rec in recommendations:
                lines.append(f"  • {rec}")
            lines.append("")
        
        lines.append("=" * 80)
        
        return "\n".join(lines)


# Example usage and testing
if __name__ == "__main__":
    # Initialize localizer
    localizer = CodeLocalizer("/home/sakthi/PROJECTS/ccp")
    
    # Example incident
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
    at com.example.web.RequestHandler.dispatch(RequestHandler.java:89)
        """,
        "logs": """
2026-01-01 10:00:15 [payment-service] INFO: Processing payment request
2026-01-01 10:00:16 [payment-service] ERROR: NullPointerException in PaymentService.processPayment
2026-01-01 10:00:17 [payment-service] ERROR: Unable to process payment
        """
    }
    
    # Localize code
    print("Localizing code from incident...\n")
    result = localizer.localize_from_incident(incident)
    
    # Print report
    print(localizer.generate_report(result))
