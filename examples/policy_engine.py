# Policy Engine - Manages fix approval and safety policies
# Save as policy_engine.py

import logging
import yaml
from typing import Dict, List, Optional
from datetime import datetime

logging.basicConfig(level=logging.INFO)

class PolicyEngine:
    """
    Manages policies for fix approval and safety
    Determines which fixes can be automatically applied
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize policy engine
        
        Args:
            config_path: Path to policy configuration file
        """
        self.config = self._load_default_config()
        
        if config_path:
            self._load_config(config_path)
    
    def _load_default_config(self) -> Dict:
        """Load default policy configuration"""
        return {
            'auto_fix_enabled': True,
            'safety_thresholds': {
                'high': {'auto_approve': True, 'require_review': False},
                'medium': {'auto_approve': False, 'require_review': True},
                'low': {'auto_approve': False, 'require_review': True}
            },
            'service_policies': {
                'critical_services': ['payment-service', 'auth-service'],
                'allow_auto_fix': ['api-gateway', 'frontend', 'cache-service']
            },
            'error_policies': {
                'auto_fix_errors': [
                    'NullPointerException',
                    'AttributeError',
                    'TypeError',
                    'KeyError'
                ],
                'manual_review_errors': [
                    'OutOfMemoryError',
                    'SecurityException',
                    'AuthenticationException'
                ]
            },
            'time_restrictions': {
                'business_hours_only': False,
                'maintenance_window_only': False
            },
            'limits': {
                'max_auto_fixes_per_hour': 10,
                'max_auto_fixes_per_service': 3,
                'cooldown_minutes': 30
            },
            'approval_chain': {
                'high_impact_services': ['payment-service', 'auth-service'],
                'approvers': ['team-lead', 'senior-dev']
            }
        }
    
    def _load_config(self, config_path: str):
        """Load policy configuration from file with environment variable expansion"""
        try:
            from config_loader import load_config
            custom_config = load_config(config_path)
            self.config.update(custom_config)
            logging.info(f"Loaded policy config from {config_path}")
        except Exception as e:
            logging.error(f"Failed to load config: {e}")
    
    def can_auto_fix(self, fix_request: Dict) -> Dict:
        """
        Determine if a fix can be automatically applied
        
        Args:
            fix_request: Dict containing:
                - service: service name
                - error_type: type of error
                - safety_level: high/medium/low
                - template_id: fix template ID
                - confidence_score: RCA confidence score
        
        Returns:
            Dict with decision and reasoning
        """
        decision = {
            'approved': False,
            'reason': '',
            'requires_review': False,
            'restrictions': []
        }
        
        # Check if auto-fix is globally enabled
        if not self.config['auto_fix_enabled']:
            decision['reason'] = "Auto-fix is globally disabled"
            decision['requires_review'] = True
            return decision
        
        # Check service policy
        service = fix_request.get('service')
        if service in self.config['service_policies']['critical_services']:
            decision['reason'] = f"Service '{service}' is critical - requires review"
            decision['requires_review'] = True
            return decision
        
        # Check safety level
        safety_level = fix_request.get('safety_level', 'medium')
        safety_policy = self.config['safety_thresholds'].get(safety_level, {})
        
        if not safety_policy.get('auto_approve', False):
            decision['reason'] = f"Safety level '{safety_level}' requires manual approval"
            decision['requires_review'] = True
            return decision
        
        # Check error type policy
        error_type = fix_request.get('error_type')
        if error_type in self.config['error_policies']['manual_review_errors']:
            decision['reason'] = f"Error type '{error_type}' requires manual review"
            decision['requires_review'] = True
            return decision
        
        # Check confidence score
        confidence_score = fix_request.get('confidence_score', 0)
        if confidence_score < 0.7:
            decision['reason'] = f"Confidence score too low ({confidence_score:.2f} < 0.70)"
            decision['requires_review'] = True
            return decision
        
        # Check rate limits
        rate_limit_check = self._check_rate_limits(service)
        if not rate_limit_check['allowed']:
            decision['reason'] = rate_limit_check['reason']
            decision['requires_review'] = True
            return decision
        
        # All checks passed
        decision['approved'] = True
        decision['reason'] = "All policy checks passed"
        
        # Add any restrictions
        if safety_policy.get('require_review'):
            decision['requires_review'] = True
        
        return decision
    
    def _check_rate_limits(self, service: str) -> Dict:
        """Check if rate limits are exceeded"""
        # In production, track actual fix history
        # For now, always allow
        return {
            'allowed': True,
            'reason': 'Within rate limits'
        }
    
    def requires_approval(self, fix_request: Dict) -> bool:
        """Check if fix requires human approval"""
        decision = self.can_auto_fix(fix_request)
        return decision['requires_review'] or not decision['approved']
    
    def validate_fix_context(self, fix_request: Dict) -> Dict:
        """
        Validate the context in which fix will be applied
        
        Returns validation result with warnings/errors
        """
        validation = {
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        # Required fields
        required_fields = ['service', 'error_type', 'file_path', 'template_id']
        for field in required_fields:
            if not fix_request.get(field):
                validation['valid'] = False
                validation['errors'].append(f"Missing required field: {field}")
        
        # Validate service
        service = fix_request.get('service')
        if service and service in self.config['service_policies']['critical_services']:
            validation['warnings'].append(
                f"Service '{service}' is critical - extra caution required"
            )
        
        # Validate file path
        file_path = fix_request.get('file_path', '')
        if 'test' in file_path.lower():
            validation['warnings'].append("Modifying test file")
        
        # Check for recent changes
        if fix_request.get('recent_commit_hours', 0) < 1:
            validation['warnings'].append(
                "File was recently modified - may conflict with ongoing work"
            )
        
        return validation
    
    def get_approval_chain(self, service: str) -> List[str]:
        """Get list of approvers for a service"""
        if service in self.config['approval_chain']['high_impact_services']:
            return self.config['approval_chain']['approvers']
        return []
    
    def log_fix_decision(self, fix_request: Dict, decision: Dict):
        """Log fix decision for audit trail"""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'service': fix_request.get('service'),
            'error_type': fix_request.get('error_type'),
            'template_id': fix_request.get('template_id'),
            'decision': decision['approved'],
            'reason': decision['reason'],
            'requires_review': decision['requires_review']
        }
        
        logging.info(f"Fix Decision: {log_entry}")
        
        # In production, write to audit log file/database
        return log_entry
    
    def update_policy(self, policy_updates: Dict):
        """Update policy configuration dynamically"""
        self.config.update(policy_updates)
        logging.info(f"Updated policy configuration: {policy_updates}")


# Example usage and testing
if __name__ == "__main__":
    # Initialize policy engine
    engine = PolicyEngine()
    
    # Test fix requests
    test_requests = [
        {
            'service': 'api-gateway',
            'error_type': 'NullPointerException',
            'safety_level': 'high',
            'template_id': 'java-null-check',
            'confidence_score': 0.85,
            'file_path': 'src/main/java/Gateway.java'
        },
        {
            'service': 'payment-service',
            'error_type': 'NullPointerException',
            'safety_level': 'high',
            'template_id': 'java-null-check',
            'confidence_score': 0.85,
            'file_path': 'src/main/java/PaymentService.java'
        },
        {
            'service': 'api-gateway',
            'error_type': 'OutOfMemoryError',
            'safety_level': 'low',
            'template_id': 'memory-fix',
            'confidence_score': 0.65,
            'file_path': 'src/main/java/Gateway.java'
        }
    ]
    
    print("Policy Engine Test Results:")
    print("=" * 80)
    
    for i, request in enumerate(test_requests, 1):
        print(f"\nTest {i}: {request['service']} - {request['error_type']}")
        
        # Check if can auto-fix
        decision = engine.can_auto_fix(request)
        print(f"  Auto-fix approved: {decision['approved']}")
        print(f"  Reason: {decision['reason']}")
        print(f"  Requires review: {decision['requires_review']}")
        
        # Validate context
        validation = engine.validate_fix_context(request)
        print(f"  Valid: {validation['valid']}")
        if validation['warnings']:
            print(f"  Warnings: {', '.join(validation['warnings'])}")
        if validation['errors']:
            print(f"  Errors: {', '.join(validation['errors'])}")
        
        # Log decision
        engine.log_fix_decision(request, decision)
