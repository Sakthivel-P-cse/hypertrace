# Fix Planner - Main orchestrator for fix planning
# Integrates RCA results, code localization, templates, and policies
# Save as fix_planner.py

import logging
from typing import Dict, List, Optional
from fix_template_manager import FixTemplateManager
from policy_engine import PolicyEngine

logging.basicConfig(level=logging.INFO)

class FixPlanner:
    """
    Main fix planner that:
    1. Receives RCA results and code localization
    2. Selects appropriate fix templates
    3. Validates against policies
    4. Generates fix plans for approval
    """
    
    def __init__(self, templates_path: str = "fix_templates.yaml", 
                 policy_config: Optional[str] = None):
        """
        Initialize fix planner
        
        Args:
            templates_path: Path to fix templates file
            policy_config: Path to policy configuration
        """
        self.template_manager = FixTemplateManager(templates_path)
        self.policy_engine = PolicyEngine(policy_config)
    
    def plan_fix(self, incident_data: Dict, rca_result: Dict, 
                 code_location: Dict) -> Dict:
        """
        Create a fix plan for an incident
        
        Args:
            incident_data: Original incident data
            rca_result: RCA analysis result
            code_location: Code localization result
        
        Returns:
            Fix plan with template, context, and approval status
        """
        fix_plan = {
            'incident_id': incident_data.get('trace_id', 'unknown'),
            'service': incident_data.get('service'),
            'error_type': incident_data.get('error_type'),
            'timestamp': incident_data.get('timestamp'),
            'fixes': [],
            'overall_status': 'pending',
            'requires_approval': False
        }
        
        # Extract root cause location
        root_cause = code_location.get('root_cause_location')
        
        if not root_cause or not root_cause.get('exists'):
            fix_plan['overall_status'] = 'failed'
            fix_plan['reason'] = 'Unable to localize code - file not found'
            return fix_plan
        
        # Get language from code location
        language = root_cause.get('language', 'unknown')
        error_type = incident_data.get('error_type', 'Unknown')
        
        # Find matching fix templates
        matching_templates = self.template_manager.find_matching_templates(
            error_type, 
            language
        )
        
        if not matching_templates:
            fix_plan['overall_status'] = 'failed'
            fix_plan['reason'] = f'No fix templates found for {error_type} in {language}'
            return fix_plan
        
        # Create fix for each matching template
        for template in matching_templates[:3]:  # Top 3 templates
            fix = self._create_fix(
                template,
                root_cause,
                incident_data,
                rca_result
            )
            
            if fix:
                fix_plan['fixes'].append(fix)
        
        # Get top fix
        if fix_plan['fixes']:
            top_fix = fix_plan['fixes'][0]
            
            # Check policy approval
            fix_request = {
                'service': fix_plan['service'],
                'error_type': fix_plan['error_type'],
                'safety_level': top_fix['safety_level'],
                'template_id': top_fix['template_id'],
                'confidence_score': rca_result.get('probable_root_causes', [{}])[0].get('confidence_score', 0),
                'file_path': root_cause.get('absolute_path')
            }
            
            policy_decision = self.policy_engine.can_auto_fix(fix_request)
            
            fix_plan['policy_decision'] = policy_decision
            fix_plan['requires_approval'] = policy_decision['requires_review'] or not policy_decision['approved']
            fix_plan['overall_status'] = 'ready' if policy_decision['approved'] else 'requires_approval'
            
            # Log decision
            self.policy_engine.log_fix_decision(fix_request, policy_decision)
        else:
            fix_plan['overall_status'] = 'failed'
            fix_plan['reason'] = 'Unable to create fix from templates'
        
        return fix_plan
    
    def _create_fix(self, template: Dict, root_cause: Dict, 
                    incident_data: Dict, rca_result: Dict) -> Optional[Dict]:
        """Create a fix from a template and context"""
        
        # Build context for template rendering
        context = self._build_template_context(root_cause, incident_data)
        
        # Validate template context
        validation = self.template_manager.validate_template_context(template, context)
        
        if not validation['valid']:
            logging.warning(f"Template {template['id']} missing variables: {validation['missing_variables']}")
            # Try to provide defaults for missing variables
            for var in validation['missing_variables']:
                if var not in context:
                    context[var] = f"<{var}>"
        
        # Render template
        try:
            rendered_fix = self.template_manager.render_template(template, context)
        except Exception as e:
            logging.error(f"Failed to render template: {e}")
            return None
        
        # Create fix object
        fix = {
            'template_id': template['id'],
            'template_name': template['name'],
            'description': template['description'],
            'safety_level': template.get('safety_level', 'medium'),
            'requires_review': template.get('requires_review', True),
            'test_required': template.get('test_required', True),
            'language': template.get('language'),
            'file_path': root_cause.get('absolute_path'),
            'line_number': root_cause.get('line'),
            'function_name': root_cause.get('method') or root_cause.get('function'),
            'rendered_fix': rendered_fix,
            'context': context,
            'original_code': self._get_original_code(root_cause)
        }
        
        return fix
    
    def _build_template_context(self, root_cause: Dict, incident_data: Dict) -> Dict:
        """Build context variables for template rendering"""
        context = {}
        
        # Extract variable name from code context
        code_context = root_cause.get('code_context', {})
        if code_context:
            target_lines = [line for line in code_context.get('lines', []) 
                          if line.get('is_target')]
            if target_lines:
                target_line = target_lines[0]
                context['original_line'] = target_line['content'].strip()
                
                # Try to extract variable name (simple heuristic)
                import re
                var_match = re.search(r'(\w+)\.\w+\(', target_line['content'])
                if var_match:
                    context['variable'] = var_match.group(1)
        
        # Add metadata
        context['function_name'] = root_cause.get('method') or root_cause.get('function', 'unknown')
        context['exception_type'] = incident_data.get('error_type', 'Exception')
        context['operation'] = f"execute {context['function_name']}"
        
        # Add defaults
        context.setdefault('variable', 'object')
        context.setdefault('original_line', '// Original code here')
        
        return context
    
    def _get_original_code(self, root_cause: Dict) -> str:
        """Get original code snippet"""
        code_context = root_cause.get('code_context', {})
        if code_context:
            lines = code_context.get('lines', [])
            return '\n'.join(line['content'] for line in lines)
        return ''
    
    def generate_fix_report(self, fix_plan: Dict) -> str:
        """Generate human-readable fix plan report"""
        lines = []
        lines.append("=" * 80)
        lines.append("FIX PLAN REPORT")
        lines.append("=" * 80)
        lines.append("")
        
        # Incident info
        lines.append(f"Incident ID: {fix_plan.get('incident_id')}")
        lines.append(f"Service:     {fix_plan.get('service')}")
        lines.append(f"Error Type:  {fix_plan.get('error_type')}")
        lines.append(f"Status:      {fix_plan.get('overall_status')}")
        lines.append(f"Requires Approval: {fix_plan.get('requires_approval')}")
        lines.append("")
        
        # Policy decision
        if 'policy_decision' in fix_plan:
            decision = fix_plan['policy_decision']
            lines.append("POLICY DECISION:")
            lines.append(f"  Approved:        {decision.get('approved')}")
            lines.append(f"  Reason:          {decision.get('reason')}")
            lines.append(f"  Requires Review: {decision.get('requires_review')}")
            lines.append("")
        
        # Proposed fixes
        fixes = fix_plan.get('fixes', [])
        if fixes:
            lines.append(f"PROPOSED FIXES ({len(fixes)} options):")
            lines.append("")
            
            for i, fix in enumerate(fixes, 1):
                lines.append(f"{i}. {fix['template_name']} (ID: {fix['template_id']})")
                lines.append(f"   Description:  {fix['description']}")
                lines.append(f"   Safety Level: {fix['safety_level']}")
                lines.append(f"   File:         {fix.get('file_path', 'unknown')}")
                lines.append(f"   Line:         {fix.get('line_number', 'unknown')}")
                lines.append(f"   Function:     {fix.get('function_name', 'unknown')}")
                lines.append("")
                
                if i == 1:  # Show rendered fix for top candidate
                    lines.append("   Rendered Fix:")
                    for line in fix['rendered_fix'].split('\n'):
                        lines.append(f"   {line}")
                    lines.append("")
        else:
            lines.append("NO FIXES AVAILABLE")
            if 'reason' in fix_plan:
                lines.append(f"Reason: {fix_plan['reason']}")
            lines.append("")
        
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def batch_plan_fixes(self, incidents: List[Dict]) -> List[Dict]:
        """Plan fixes for multiple incidents"""
        fix_plans = []
        
        for incident in incidents:
            # Assuming incidents already have RCA and code location
            try:
                fix_plan = self.plan_fix(
                    incident.get('incident_data', {}),
                    incident.get('rca_result', {}),
                    incident.get('code_location', {})
                )
                fix_plans.append(fix_plan)
            except Exception as e:
                logging.error(f"Failed to plan fix: {e}")
                fix_plans.append({
                    'error': str(e),
                    'incident': incident
                })
        
        return fix_plans


# Example usage and testing
if __name__ == "__main__":
    # Initialize fix planner
    planner = FixPlanner("fix_templates.yaml")
    
    # Example incident data
    incident = {
        'trace_id': 'trace-abc-123',
        'service': 'api-gateway',
        'error_type': 'NullPointerException',
        'timestamp': '2026-01-01T10:00:00'
    }
    
    # Example RCA result
    rca_result = {
        'probable_root_causes': [
            {
                'service': 'api-gateway',
                'confidence_score': 0.85
            }
        ]
    }
    
    # Example code location
    code_location = {
        'root_cause_location': {
            'language': 'java',
            'file': 'Gateway.java',
            'absolute_path': '/home/sakthi/PROJECTS/ccp/examples/Gateway.java',
            'line': 42,
            'method': 'handleRequest',
            'exists': True,
            'code_context': {
                'lines': [
                    {'line_number': 40, 'content': '  public void handleRequest(Request req) {', 'is_target': False},
                    {'line_number': 41, 'content': '    User user = req.getUser();', 'is_target': False},
                    {'line_number': 42, 'content': '    String name = user.getName();', 'is_target': True},
                    {'line_number': 43, 'content': '    processRequest(name);', 'is_target': False}
                ]
            }
        }
    }
    
    # Plan fix
    print("Planning fix...\n")
    fix_plan = planner.plan_fix(incident, rca_result, code_location)
    
    # Print report
    print(planner.generate_fix_report(fix_plan))
