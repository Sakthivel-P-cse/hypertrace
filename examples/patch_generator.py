"""
Patch Generator
Main orchestrator that generates and applies code patches from fix plans.
Integrates with Fix Planner (Step 5), Patch Validator, and Patch Applier.
"""

import sys
import json
from typing import Dict, List, Any, Optional
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime

# Import Step 5 components
sys.path.insert(0, str(Path(__file__).parent))
from fix_planner import FixPlanner
from patch_validator import PatchValidator, ValidationLevel
from patch_applier import PatchApplier, PatchResult


@dataclass
class PatchPlan:
    """A plan for generating and applying patches"""
    incident_id: str
    fixes: List[Dict[str, Any]]
    total_files: int
    estimated_risk: str  # low, medium, high
    requires_approval: bool
    validation_level: str


@dataclass
class PatchGenerationResult:
    """Result of patch generation process"""
    success: bool
    incident_id: str
    patches_generated: int
    patches_applied: int
    patches_failed: int
    validation_issues: List[Dict[str, Any]]
    patch_results: List[Dict[str, Any]]
    commit_hashes: List[str]
    duration_seconds: float
    error: Optional[str] = None


class PatchGenerator:
    """
    Main patch generation orchestrator.
    
    Workflow:
    1. Receive fix plan from Fix Planner (Step 5)
    2. Generate code patches by applying templates
    3. Validate patches for safety and correctness
    4. Apply patches to files (with Git commits)
    5. Return detailed results
    
    Features:
    - Template-based code generation
    - Multi-language support
    - Safety validation
    - Dry-run mode
    - Batch processing
    - Rollback support
    """
    
    def __init__(
        self,
        repo_path: str,
        fix_planner: FixPlanner,
        config: Optional[Dict[str, Any]] = None
    ):
        self.repo_path = Path(repo_path)
        self.fix_planner = fix_planner
        self.config = config or {}
        
        # Initialize validators and appliers
        self.validator = PatchValidator({
            'validation_level': self.config.get('validation_level', 'normal'),
            'max_lines_changed': self.config.get('max_lines_changed', 500)
        })
        
        self.applier = PatchApplier(str(self.repo_path), {
            'auto_commit': self.config.get('auto_commit', True),
            'create_backups': self.config.get('create_backups', True)
        })
        
        self.dry_run = self.config.get('dry_run', False)
    
    def generate_patches_from_plan(
        self,
        fix_plan: Dict[str, Any],
        dry_run: Optional[bool] = None
    ) -> PatchGenerationResult:
        """
        Generate and apply patches from a fix plan.
        
        Args:
            fix_plan: Fix plan from FixPlanner
            dry_run: Override default dry_run setting
            
        Returns:
            PatchGenerationResult with detailed outcomes
        """
        start_time = datetime.now()
        
        if dry_run is None:
            dry_run = self.dry_run
        
        incident_id = fix_plan.get('incident_id', 'unknown')
        fixes = fix_plan.get('fixes', [])
        
        if not fixes:
            return PatchGenerationResult(
                success=False,
                incident_id=incident_id,
                patches_generated=0,
                patches_applied=0,
                patches_failed=0,
                validation_issues=[],
                patch_results=[],
                commit_hashes=[],
                duration_seconds=0,
                error="No fixes in plan"
            )
        
        patches_generated = []
        validation_issues_all = []
        patch_results = []
        commit_hashes = []
        
        # Step 1: Generate patches from templates
        for fix in fixes:
            try:
                patch = self._generate_patch_from_fix(fix)
                if patch:
                    patches_generated.append(patch)
            except Exception as e:
                validation_issues_all.append({
                    'fix_id': fix.get('fix_id'),
                    'error': f"Patch generation failed: {str(e)}"
                })
        
        if not patches_generated:
            return PatchGenerationResult(
                success=False,
                incident_id=incident_id,
                patches_generated=0,
                patches_applied=0,
                patches_failed=0,
                validation_issues=validation_issues_all,
                patch_results=[],
                commit_hashes=[],
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                error="No patches generated"
            )
        
        # Step 2: Validate all patches
        validated_patches = []
        for patch in patches_generated:
            is_valid, issues = self.validator.validate_patch(
                patch['original_content'],
                patch['patched_content'],
                patch['file_path'],
                patch['language']
            )
            
            patch['is_valid'] = is_valid
            patch['validation_issues'] = [
                {
                    'level': issue.level.value,
                    'check': issue.check,
                    'message': issue.message,
                    'line_number': issue.line_number
                }
                for issue in issues
            ]
            
            if is_valid:
                validated_patches.append(patch)
            else:
                validation_issues_all.extend(patch['validation_issues'])
        
        if not validated_patches:
            return PatchGenerationResult(
                success=False,
                incident_id=incident_id,
                patches_generated=len(patches_generated),
                patches_applied=0,
                patches_failed=len(patches_generated),
                validation_issues=validation_issues_all,
                patch_results=[],
                commit_hashes=[],
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                error="No patches passed validation"
            )
        
        # Step 3: Apply patches
        applied_count = 0
        failed_count = 0
        
        for patch in validated_patches:
            result = self.applier.apply_patch(
                patch['file_path'],
                patch['original_content'],
                patch['patched_content'],
                dry_run=dry_run,
                commit_message=patch.get('commit_message', f"Auto-fix: {patch['file_path']}")
            )
            
            patch_results.append({
                'file_path': result.file_path,
                'success': result.success,
                'lines_added': result.lines_added,
                'lines_removed': result.lines_removed,
                'commit_hash': result.commit_hash,
                'error': result.error,
                'diff': result.diff
            })
            
            if result.success:
                applied_count += 1
                if result.commit_hash:
                    commit_hashes.append(result.commit_hash)
            else:
                failed_count += 1
        
        duration = (datetime.now() - start_time).total_seconds()
        
        return PatchGenerationResult(
            success=(failed_count == 0),
            incident_id=incident_id,
            patches_generated=len(patches_generated),
            patches_applied=applied_count,
            patches_failed=failed_count,
            validation_issues=validation_issues_all,
            patch_results=patch_results,
            commit_hashes=commit_hashes,
            duration_seconds=duration
        )
    
    def generate_patches_from_incident(
        self,
        incident_data: Dict[str, Any],
        rca_result: Dict[str, Any],
        code_location: Dict[str, Any],
        dry_run: Optional[bool] = None
    ) -> PatchGenerationResult:
        """
        End-to-end: Generate patches from incident data.
        
        This method integrates with the entire pipeline:
        - Calls Fix Planner to create fix plan
        - Generates patches from the plan
        - Validates and applies patches
        
        Args:
            incident_data: Original incident data
            rca_result: RCA analysis result
            code_location: Code localization result
            dry_run: Override default dry_run setting
            
        Returns:
            PatchGenerationResult
        """
        # Step 1: Get fix plan from Fix Planner
        fix_plan = self.fix_planner.plan_fix(
            incident_data,
            rca_result,
            code_location
        )
        
        if not fix_plan.get('fixes'):
            return PatchGenerationResult(
                success=False,
                incident_id=incident_data.get('incident_id', 'unknown'),
                patches_generated=0,
                patches_applied=0,
                patches_failed=0,
                validation_issues=[],
                patch_results=[],
                commit_hashes=[],
                duration_seconds=0,
                error="Fix planner returned no fixes"
            )
        
        # Step 2: Generate and apply patches
        return self.generate_patches_from_plan(fix_plan, dry_run)
    
    def _generate_patch_from_fix(self, fix: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Generate a patch from a single fix.
        
        Args:
            fix: Fix dict from FixPlanner
            
        Returns:
            Patch dict with original/patched content
        """
        file_path = fix.get('target_file')
        if not file_path:
            return None
        
        full_path = self.repo_path / file_path
        
        # Read original file
        if not full_path.exists():
            return None
        
        try:
            original_content = full_path.read_text(encoding='utf-8')
        except Exception:
            return None
        
        # Apply template to generate patched content
        patched_content = self._apply_template_to_code(
            original_content,
            fix
        )
        
        if not patched_content or patched_content == original_content:
            return None
        
        return {
            'fix_id': fix.get('fix_id'),
            'file_path': file_path,
            'language': fix.get('language', 'unknown'),
            'original_content': original_content,
            'patched_content': patched_content,
            'template_id': fix.get('template_id'),
            'commit_message': f"Auto-fix: {fix.get('description', 'Apply fix')}"
        }
    
    def _apply_template_to_code(
        self,
        code: str,
        fix: Dict[str, Any]
    ) -> Optional[str]:
        """
        Apply a fix template to code.
        
        This is a simplified implementation. In production, you would:
        - Parse the code into an AST
        - Locate the exact location to apply the fix
        - Apply the template intelligently
        - Regenerate code from AST
        
        For now, we do simple string substitution based on target location.
        """
        template = fix.get('template')
        target_location = fix.get('target_location', {})
        
        if not template:
            return None
        
        # Extract target information
        line_number = target_location.get('line_number')
        function_name = target_location.get('function')
        
        if not line_number:
            return None
        
        lines = code.splitlines(keepends=True)
        
        # Simple implementation: insert template at target line
        # In production, use AST manipulation
        
        if line_number <= len(lines):
            # Get indentation of target line
            target_line = lines[line_number - 1]
            indent = len(target_line) - len(target_line.lstrip())
            indent_str = ' ' * indent
            
            # Apply indentation to template
            template_lines = template.split('\n')
            indented_template = '\n'.join(
                indent_str + line if line.strip() else line
                for line in template_lines
            )
            
            # Insert template
            lines.insert(line_number - 1, indented_template + '\n')
            
            return ''.join(lines)
        
        return None
    
    def rollback_patches(self, commit_hashes: List[str]) -> bool:
        """
        Rollback patches by reverting commits.
        
        Args:
            commit_hashes: List of commit hashes to revert
            
        Returns:
            True if all rollbacks succeeded
        """
        success = True
        for commit_hash in reversed(commit_hashes):
            if not self.applier.rollback(commit_hash):
                success = False
                break
        return success
    
    def generate_report(self, result: PatchGenerationResult) -> str:
        """Generate a human-readable report"""
        report = []
        report.append("=" * 80)
        report.append("PATCH GENERATION REPORT")
        report.append("=" * 80)
        report.append(f"Incident ID: {result.incident_id}")
        report.append(f"Status: {'SUCCESS' if result.success else 'FAILED'}")
        report.append(f"Duration: {result.duration_seconds:.2f}s")
        report.append("")
        
        report.append(f"Patches Generated: {result.patches_generated}")
        report.append(f"Patches Applied: {result.patches_applied}")
        report.append(f"Patches Failed: {result.patches_failed}")
        report.append("")
        
        if result.commit_hashes:
            report.append("Git Commits:")
            for commit in result.commit_hashes:
                report.append(f"  - {commit}")
            report.append("")
        
        if result.validation_issues:
            report.append("Validation Issues:")
            for issue in result.validation_issues[:10]:  # Limit to 10
                report.append(f"  - {issue}")
            report.append("")
        
        if result.patch_results:
            report.append("Patch Details:")
            for patch in result.patch_results:
                status = "✓" if patch['success'] else "✗"
                report.append(f"  {status} {patch['file_path']}")
                report.append(f"    +{patch['lines_added']} -{patch['lines_removed']} lines")
                if patch.get('error'):
                    report.append(f"    Error: {patch['error']}")
            report.append("")
        
        if result.error:
            report.append(f"Error: {result.error}")
        
        report.append("=" * 80)
        return "\n".join(report)


# Example usage
if __name__ == "__main__":
    # Mock setup
    from fix_template_manager import FixTemplateManager
    from policy_engine import PolicyEngine
    
    # Create mock directories
    import tempfile
    import shutil
    import subprocess
    
    test_dir = Path(tempfile.mkdtemp())
    print(f"Test directory: {test_dir}")
    
    # Initialize Git repo
    subprocess.run(['git', 'init'], cwd=test_dir, capture_output=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=test_dir, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=test_dir, capture_output=True)
    
    # Create a test file
    test_file = test_dir / "service.py"
    test_file.write_text('''
def fetch_data(url):
    response = requests.get(url)
    return response.json()

def process():
    data = fetch_data("http://api.example.com")
    print(data)
''')
    
    subprocess.run(['git', 'add', 'service.py'], cwd=test_dir, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'Initial commit'], cwd=test_dir, capture_output=True)
    
    # Create Fix Planner
    template_mgr = FixTemplateManager(str(Path(__file__).parent / "fix_templates.yaml"))
    policy_engine = PolicyEngine({
        'auto_fix_enabled': True,
        'safety_thresholds': {'high': 0.95, 'medium': 0.85, 'low': 0.70}
    })
    fix_planner = FixPlanner(template_mgr, policy_engine)
    
    # Create Patch Generator
    generator = PatchGenerator(
        str(test_dir),
        fix_planner,
        config={
            'validation_level': 'normal',
            'auto_commit': True,
            'dry_run': True  # Safe mode for demo
        }
    )
    
    # Mock incident data
    incident_data = {
        'incident_id': 'INC-001',
        'service': 'api-service',
        'error_type': 'TimeoutError',
        'severity': 'high'
    }
    
    # Mock RCA result
    rca_result = {
        'root_causes': [
            {
                'service': 'api-service',
                'component': 'http_client',
                'confidence_score': 0.92,
                'reasoning': 'No timeout configured for HTTP requests'
            }
        ]
    }
    
    # Mock code location
    code_location = {
        'primary_location': {
            'file': 'service.py',
            'line_number': 3,
            'function': 'fetch_data',
            'code_snippet': 'response = requests.get(url)'
        }
    }
    
    # Generate patches
    print("\n=== GENERATING PATCHES ===")
    result = generator.generate_patches_from_incident(
        incident_data,
        rca_result,
        code_location,
        dry_run=True
    )
    
    print(generator.generate_report(result))
    
    # Cleanup
    shutil.rmtree(test_dir)
    print(f"\nCleaned up test directory")
