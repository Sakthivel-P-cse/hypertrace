# Fix Template Manager - Loads and manages fix templates
# Save as fix_template_manager.py

import yaml
import re
import logging
from typing import List, Dict, Optional

logging.basicConfig(level=logging.INFO)

class FixTemplateManager:
    """Manages fix templates and selects appropriate fixes for errors"""
    
    def __init__(self, templates_path: str = "fix_templates.yaml"):
        """
        Initialize template manager
        
        Args:
            templates_path: Path to fix templates YAML file
        """
        self.templates_path = templates_path
        self.templates = []
        self.selection_rules = []
        self._load_templates()
    
    def _load_templates(self):
        """Load fix templates from YAML file"""
        try:
            with open(self.templates_path, 'r') as f:
                data = yaml.safe_load(f)
                self.templates = data.get('templates', [])
                self.selection_rules = data.get('selection_rules', [])
            
            logging.info(f"Loaded {len(self.templates)} fix templates")
        except Exception as e:
            logging.error(f"Failed to load templates: {e}")
            self.templates = []
    
    def find_matching_templates(self, error_type: str, language: str) -> List[Dict]:
        """
        Find templates that match the error type and language
        
        Args:
            error_type: Type of error (e.g., 'NullPointerException')
            language: Programming language (e.g., 'java', 'python')
        
        Returns:
            List of matching templates
        """
        matching = []
        
        for template in self.templates:
            # Check language match
            template_lang = template.get('language', '*')
            if template_lang != '*' and template_lang != language:
                continue
            
            # Check error type match
            error_types = template.get('error_types', [])
            
            # Check for exact match or wildcard
            if '*' in error_types or error_type in error_types:
                matching.append(template)
                continue
            
            # Check for partial match (e.g., 'Exception' matches 'NullPointerException')
            for template_error in error_types:
                if template_error in error_type or error_type in template_error:
                    matching.append(template)
                    break
        
        # Sort by safety level (high first)
        safety_order = {'high': 0, 'medium': 1, 'low': 2}
        matching.sort(key=lambda t: safety_order.get(t.get('safety_level', 'medium'), 1))
        
        return matching
    
    def get_template_by_id(self, template_id: str) -> Optional[Dict]:
        """Get a specific template by ID"""
        for template in self.templates:
            if template.get('id') == template_id:
                return template
        return None
    
    def render_template(self, template: Dict, context: Dict) -> str:
        """
        Render a fix template with context variables
        
        Args:
            template: Fix template dict
            context: Variables to substitute (e.g., {'variable': 'customer', 'line': 42})
        
        Returns:
            Rendered fix code
        """
        fix_code = template.get('fix_template', '')
        
        # Replace template variables with context values
        for key, value in context.items():
            placeholder = f"{{{{{key}}}}}"
            fix_code = fix_code.replace(placeholder, str(value))
        
        return fix_code
    
    def validate_template_context(self, template: Dict, context: Dict) -> Dict:
        """
        Validate that context has all required variables for template
        
        Returns validation result
        """
        validation = {
            'valid': True,
            'missing_variables': []
        }
        
        fix_template = template.get('fix_template', '')
        
        # Extract required variables from template
        required_vars = re.findall(r'{{(\w+)}}', fix_template)
        
        for var in required_vars:
            if var not in context:
                validation['valid'] = False
                validation['missing_variables'].append(var)
        
        return validation
    
    def get_template_metadata(self, template_id: str) -> Optional[Dict]:
        """Get metadata about a template"""
        template = self.get_template_by_id(template_id)
        
        if not template:
            return None
        
        return {
            'id': template.get('id'),
            'name': template.get('name'),
            'language': template.get('language'),
            'safety_level': template.get('safety_level'),
            'requires_review': template.get('requires_review'),
            'test_required': template.get('test_required'),
            'description': template.get('description')
        }
    
    def list_templates(self, language: Optional[str] = None, 
                      safety_level: Optional[str] = None) -> List[Dict]:
        """
        List available templates with optional filtering
        
        Args:
            language: Filter by language
            safety_level: Filter by safety level
        
        Returns:
            List of template metadata
        """
        filtered = self.templates
        
        if language:
            filtered = [t for t in filtered if t.get('language') in [language, '*']]
        
        if safety_level:
            filtered = [t for t in filtered if t.get('safety_level') == safety_level]
        
        return [self.get_template_metadata(t['id']) for t in filtered]


# Example usage and testing
if __name__ == "__main__":
    # Initialize template manager
    manager = FixTemplateManager("fix_templates.yaml")
    
    # Test 1: Find templates for Java NullPointerException
    print("Test 1: Finding templates for Java NullPointerException")
    templates = manager.find_matching_templates('NullPointerException', 'java')
    print(f"Found {len(templates)} matching templates:")
    for t in templates:
        print(f"  - {t['id']}: {t['name']} (safety: {t['safety_level']})")
    print()
    
    # Test 2: Render a template
    print("Test 2: Rendering null-check template")
    template = manager.get_template_by_id('java-null-check')
    if template:
        context = {
            'variable': 'customer',
            'original_line': 'String email = customer.getEmail();'
        }
        
        rendered = manager.render_template(template, context)
        print("Rendered fix:")
        print(rendered)
    print()
    
    # Test 3: Validate template context
    print("Test 3: Validating template context")
    if template:
        # Missing 'original_line' variable
        incomplete_context = {'variable': 'customer'}
        validation = manager.validate_template_context(template, incomplete_context)
        print(f"Valid: {validation['valid']}")
        if not validation['valid']:
            print(f"Missing variables: {validation['missing_variables']}")
    print()
    
    # Test 4: List all high-safety templates
    print("Test 4: Listing high-safety templates")
    high_safety = manager.list_templates(safety_level='high')
    print(f"Found {len(high_safety)} high-safety templates:")
    for t in high_safety:
        print(f"  - {t['id']}: {t['name']} ({t['language']})")
