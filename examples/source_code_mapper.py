# Source Code Mapper - Maps stack frames to actual source code files
# Save as source_code_mapper.py

import os
import logging
from pathlib import Path
from typing import List, Dict, Optional

logging.basicConfig(level=logging.INFO)

class SourceCodeMapper:
    """Map stack frames and errors to actual source code locations"""
    
    def __init__(self, repo_path: str, source_roots: Optional[List[str]] = None):
        """
        Initialize mapper
        
        Args:
            repo_path: Root path of the repository
            source_roots: List of source root directories (e.g., ['src', 'lib', 'app'])
        """
        self.repo_path = Path(repo_path)
        self.source_roots = source_roots or ['src', 'lib', 'app', 'services']
        
        # Build file index for fast lookup
        self.file_index = self._build_file_index()
    
    def _build_file_index(self) -> Dict[str, List[Path]]:
        """Build index of all source files by name"""
        index = {}
        
        extensions = ['.java', '.py', '.js', '.ts', '.go', '.rb', '.cs', '.cpp', '.c', '.php']
        
        for ext in extensions:
            pattern = f"**/*{ext}"
            for file_path in self.repo_path.rglob(pattern):
                # Skip common non-source directories
                if any(skip in file_path.parts for skip in ['node_modules', '.git', 'target', 'build', '__pycache__']):
                    continue
                
                filename = file_path.name
                if filename not in index:
                    index[filename] = []
                index[filename].append(file_path)
        
        logging.info(f"Indexed {sum(len(v) for v in index.values())} source files")
        return index
    
    def locate_file(self, filename: str, package: Optional[str] = None) -> Optional[Path]:
        """
        Locate a source file in the repository
        
        Args:
            filename: Name of the file (e.g., 'PaymentService.java')
            package: Package/namespace (e.g., 'com.example.payment')
        
        Returns:
            Full path to the file, or None if not found
        """
        # Direct lookup in index
        candidates = self.file_index.get(filename, [])
        
        if not candidates:
            # Try without extension
            base_name = os.path.splitext(filename)[0]
            for key in self.file_index.keys():
                if os.path.splitext(key)[0] == base_name:
                    candidates.extend(self.file_index[key])
        
        if not candidates:
            return None
        
        # If package is provided, filter by package path
        if package:
            package_path = package.replace('.', os.sep)
            for candidate in candidates:
                if package_path in str(candidate):
                    return candidate
        
        # Return first candidate if no package match
        return candidates[0]
    
    def map_stack_frame(self, frame: Dict) -> Dict:
        """
        Map a stack frame to actual source code location
        
        Args:
            frame: Stack frame dict from StackTraceParser
        
        Returns:
            Enhanced frame with absolute_path and exists flag
        """
        filename = frame.get('file')
        if not filename:
            return {**frame, 'exists': False}
        
        # Get package/directory context
        package = frame.get('package')
        
        # Locate file
        file_path = self.locate_file(filename, package)
        
        if file_path:
            return {
                **frame,
                'absolute_path': str(file_path),
                'relative_path': str(file_path.relative_to(self.repo_path)),
                'exists': True
            }
        else:
            return {
                **frame,
                'exists': False,
                'error': 'File not found in repository'
            }
    
    def get_code_context(self, file_path: str, line_number: int, context_lines: int = 5) -> Optional[Dict]:
        """
        Get code context around a specific line
        
        Args:
            file_path: Absolute path to the file
            line_number: Line number (1-indexed)
            context_lines: Number of lines before/after to include
        
        Returns:
            Dict with code context, or None if file not found
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            # Calculate range
            start = max(0, line_number - context_lines - 1)
            end = min(len(lines), line_number + context_lines)
            
            # Get context lines
            context = {
                'file': file_path,
                'target_line': line_number,
                'lines': []
            }
            
            for i in range(start, end):
                context['lines'].append({
                    'line_number': i + 1,
                    'content': lines[i].rstrip('\n'),
                    'is_target': (i + 1 == line_number)
                })
            
            return context
        
        except Exception as e:
            logging.error(f"Error reading file {file_path}: {e}")
            return None
    
    def extract_function_definition(self, file_path: str, function_name: str, language: str = 'java') -> Optional[Dict]:
        """
        Extract the definition of a function/method from a file
        
        Args:
            file_path: Path to the source file
            function_name: Name of the function/method
            language: Programming language
        
        Returns:
            Dict with function details and location
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            # Language-specific patterns for function definitions
            patterns = {
                'java': rf'(public|private|protected)?\s+\w+\s+{function_name}\s*\(',
                'python': rf'def\s+{function_name}\s*\(',
                'javascript': rf'(function\s+{function_name}|{function_name}\s*=\s*function|\s+{function_name}\s*\()',
                'go': rf'func\s+{function_name}\s*\(',
                'csharp': rf'(public|private|protected)?\s+\w+\s+{function_name}\s*\(',
            }
            
            import re
            pattern = patterns.get(language, rf'{function_name}\s*\(')
            
            for i, line in enumerate(lines):
                if re.search(pattern, line):
                    # Found function definition
                    return {
                        'file': file_path,
                        'function': function_name,
                        'line_number': i + 1,
                        'definition': line.strip(),
                        'language': language
                    }
            
            return None
        
        except Exception as e:
            logging.error(f"Error extracting function from {file_path}: {e}")
            return None
    
    def find_error_prone_patterns(self, file_path: str) -> List[Dict]:
        """
        Scan a file for common error-prone patterns
        
        Returns list of potential issues
        """
        issues = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            # Common patterns to check
            patterns = [
                {
                    'pattern': r'\.get\([^)]+\)\.',
                    'message': 'Potential NullPointerException: chained method call after get()',
                    'severity': 'medium'
                },
                {
                    'pattern': r'catch\s*\([^)]*Exception[^)]*\)\s*\{\s*\}',
                    'message': 'Empty catch block - exceptions are silently ignored',
                    'severity': 'high'
                },
                {
                    'pattern': r'System\.exit\(',
                    'message': 'System.exit() call - may cause abrupt termination',
                    'severity': 'medium'
                },
                {
                    'pattern': r'TODO|FIXME|XXX',
                    'message': 'TODO/FIXME comment - potential incomplete implementation',
                    'severity': 'low'
                }
            ]
            
            import re
            for i, line in enumerate(lines):
                for check in patterns:
                    if re.search(check['pattern'], line, re.IGNORECASE):
                        issues.append({
                            'file': file_path,
                            'line': i + 1,
                            'code': line.strip(),
                            'issue': check['message'],
                            'severity': check['severity']
                        })
        
        except Exception as e:
            logging.error(f"Error scanning file {file_path}: {e}")
        
        return issues


# Example usage and testing
if __name__ == "__main__":
    # Initialize mapper (using current project)
    mapper = SourceCodeMapper("/home/sakthi/PROJECTS/ccp")
    
    # Test file lookup
    print("Testing file location...")
    test_file = mapper.locate_file("server.js")
    if test_file:
        print(f"Found: {test_file}")
    
    # Test stack frame mapping
    print("\nTesting stack frame mapping...")
    test_frame = {
        'language': 'java',
        'package': 'com.example.payment',
        'file': 'PaymentService.java',
        'line': 42,
        'method': 'processPayment'
    }
    
    mapped = mapper.map_stack_frame(test_frame)
    print(f"Mapped frame: {mapped}")
    
    # Test code context
    if test_file and test_file.exists():
        print(f"\nCode context from {test_file}:")
        context = mapper.get_code_context(str(test_file), 1, context_lines=3)
        if context:
            for line in context['lines']:
                marker = ">>>" if line['is_target'] else "   "
                print(f"{marker} {line['line_number']:4d}: {line['content']}")
