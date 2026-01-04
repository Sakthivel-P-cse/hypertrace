# Stack Trace Parser - Multi-language support
# Parses stack traces from Java, Python, JavaScript, Go, etc.
# Save as stack_trace_parser.py

import re
import logging
from typing import List, Dict, Optional

logging.basicConfig(level=logging.INFO)

class StackTraceParser:
    """Parse stack traces from various programming languages"""
    
    def __init__(self):
        # Patterns for different languages
        self.patterns = {
            'java': {
                'pattern': r'at\s+([a-zA-Z0-9_$.]+)\.([a-zA-Z0-9_$<>]+)\(([a-zA-Z0-9_$.]+\.java):(\d+)\)',
                'groups': {'class': 1, 'method': 2, 'file': 3, 'line': 4}
            },
            'python': {
                'pattern': r'File\s+"([^"]+)",\s+line\s+(\d+),\s+in\s+([a-zA-Z0-9_<>]+)',
                'groups': {'file': 1, 'line': 2, 'function': 3}
            },
            'javascript': {
                'pattern': r'at\s+(?:([a-zA-Z0-9_$.]+)\s+)?\(?([^:)]+):(\d+):(\d+)\)?',
                'groups': {'function': 1, 'file': 2, 'line': 3, 'column': 4}
            },
            'go': {
                'pattern': r'([a-zA-Z0-9_/.-]+\.go):(\d+)\s+\+0x[0-9a-f]+',
                'groups': {'file': 1, 'line': 2}
            },
            'csharp': {
                'pattern': r'at\s+([a-zA-Z0-9_.<>]+)\s+in\s+([^:]+):line\s+(\d+)',
                'groups': {'method': 1, 'file': 2, 'line': 3}
            },
            'ruby': {
                'pattern': r'([^:]+):(\d+):in\s+`([^\']+)\'',
                'groups': {'file': 1, 'line': 2, 'method': 3}
            }
        }
    
    def parse(self, stack_trace: str, language: Optional[str] = None) -> List[Dict]:
        """
        Parse stack trace and extract file locations
        
        Returns list of stack frames with:
        - file: source file path
        - line: line number
        - function/method/class: function or method name
        - language: detected language
        """
        if not stack_trace:
            return []
        
        # Auto-detect language if not specified
        if not language:
            language = self._detect_language(stack_trace)
        
        if language not in self.patterns:
            logging.warning(f"Unsupported language: {language}")
            return self._parse_generic(stack_trace)
        
        pattern_info = self.patterns[language]
        pattern = pattern_info['pattern']
        groups = pattern_info['groups']
        
        frames = []
        for match in re.finditer(pattern, stack_trace, re.MULTILINE):
            frame = {'language': language}
            
            for key, group_num in groups.items():
                value = match.group(group_num)
                if value:
                    frame[key] = value
            
            # Convert line numbers to int
            if 'line' in frame:
                frame['line'] = int(frame['line'])
            
            if 'column' in frame:
                frame['column'] = int(frame['column'])
            
            frames.append(frame)
        
        return frames
    
    def _detect_language(self, stack_trace: str) -> str:
        """Auto-detect language from stack trace format"""
        # Java
        if re.search(r'at\s+[a-zA-Z0-9_$.]+\.[a-zA-Z0-9_$<>]+\([a-zA-Z0-9_$.]+\.java:\d+\)', stack_trace):
            return 'java'
        
        # Python
        if re.search(r'File\s+"[^"]+",\s+line\s+\d+', stack_trace):
            return 'python'
        
        # JavaScript/Node.js
        if re.search(r'at\s+.*\([^:)]+:\d+:\d+\)', stack_trace):
            return 'javascript'
        
        # Go
        if re.search(r'[a-zA-Z0-9_/.-]+\.go:\d+\s+\+0x[0-9a-f]+', stack_trace):
            return 'go'
        
        # C#
        if re.search(r'at\s+[a-zA-Z0-9_.<>]+\s+in\s+[^:]+:line\s+\d+', stack_trace):
            return 'csharp'
        
        # Ruby
        if re.search(r'[^:]+:\d+:in\s+`[^\']+\'', stack_trace):
            return 'ruby'
        
        return 'unknown'
    
    def _parse_generic(self, stack_trace: str) -> List[Dict]:
        """Generic parser for unknown formats"""
        frames = []
        
        # Try to extract file:line patterns
        pattern = r'([a-zA-Z0-9_/.-]+\.[a-zA-Z0-9]+):(\d+)'
        for match in re.finditer(pattern, stack_trace):
            frames.append({
                'file': match.group(1),
                'line': int(match.group(2)),
                'language': 'unknown'
            })
        
        return frames
    
    def parse_java_stack_trace(self, stack_trace: str) -> List[Dict]:
        """Specialized Java parser with enhanced details"""
        frames = []
        
        # Match Java stack trace format
        pattern = r'at\s+([a-zA-Z0-9_$.]+)\.([a-zA-Z0-9_$<>]+)\(([a-zA-Z0-9_$.]+\.java):(\d+)\)'
        
        for match in re.finditer(pattern, stack_trace, re.MULTILINE):
            full_class = match.group(1)
            method = match.group(2)
            file = match.group(3)
            line = int(match.group(4))
            
            # Extract package and class name
            package = '.'.join(full_class.split('.')[:-1])
            class_name = full_class.split('.')[-1]
            
            frames.append({
                'language': 'java',
                'package': package,
                'class': class_name,
                'full_class': full_class,
                'method': method,
                'file': file,
                'line': line
            })
        
        return frames
    
    def parse_python_stack_trace(self, stack_trace: str) -> List[Dict]:
        """Specialized Python parser"""
        frames = []
        
        # Match Python traceback format
        pattern = r'File\s+"([^"]+)",\s+line\s+(\d+),\s+in\s+([a-zA-Z0-9_<>]+)'
        
        for match in re.finditer(pattern, stack_trace, re.MULTILINE):
            frames.append({
                'language': 'python',
                'file': match.group(1),
                'line': int(match.group(2)),
                'function': match.group(3)
            })
        
        return frames
    
    def extract_root_cause(self, frames: List[Dict]) -> Optional[Dict]:
        """Extract the most likely root cause from stack frames"""
        if not frames:
            return None
        
        # For most languages, the first frame is the root cause
        # (where the exception was actually thrown)
        return frames[0]
    
    def format_frame(self, frame: Dict) -> str:
        """Format a stack frame as a readable string"""
        if frame.get('language') == 'java':
            return f"{frame.get('full_class', 'Unknown')}.{frame.get('method', 'unknown')}({frame.get('file', 'Unknown')}:{frame.get('line', 0)})"
        elif frame.get('language') == 'python':
            return f"{frame.get('file', 'Unknown')}:{frame.get('line', 0)} in {frame.get('function', 'unknown')}"
        elif frame.get('language') == 'javascript':
            func = frame.get('function', 'anonymous')
            return f"at {func} ({frame.get('file', 'Unknown')}:{frame.get('line', 0)}:{frame.get('column', 0)})"
        else:
            return f"{frame.get('file', 'Unknown')}:{frame.get('line', 0)}"


# Example usage and testing
if __name__ == "__main__":
    parser = StackTraceParser()
    
    # Test Java stack trace
    java_trace = """
java.lang.NullPointerException: Cannot invoke method on null object
    at com.example.payment.PaymentService.processPayment(PaymentService.java:42)
    at com.example.payment.PaymentController.handleRequest(PaymentController.java:128)
    at com.example.web.RequestHandler.dispatch(RequestHandler.java:89)
    """
    
    print("Java Stack Trace:")
    frames = parser.parse(java_trace)
    for frame in frames:
        print(f"  {parser.format_frame(frame)}")
    print(f"Root cause: {parser.format_frame(parser.extract_root_cause(frames))}\n")
    
    # Test Python stack trace
    python_trace = """
Traceback (most recent call last):
  File "/app/payment_service.py", line 42, in process_payment
    result = payment.charge(amount)
  File "/app/payment.py", line 128, in charge
    response = self.api.call()
  File "/app/api_client.py", line 89, in call
    return self.connection.execute()
    """
    
    print("Python Stack Trace:")
    frames = parser.parse(python_trace)
    for frame in frames:
        print(f"  {parser.format_frame(frame)}")
    print(f"Root cause: {parser.format_frame(parser.extract_root_cause(frames))}\n")
    
    # Test JavaScript stack trace
    js_trace = """
Error: Cannot read property 'value' of undefined
    at PaymentService.processPayment (/app/services/payment.js:42:15)
    at /app/controllers/payment.js:128:23
    at RequestHandler.dispatch (/app/handlers/request.js:89:10)
    """
    
    print("JavaScript Stack Trace:")
    frames = parser.parse(js_trace)
    for frame in frames:
        print(f"  {parser.format_frame(frame)}")
    if frames:
        print(f"Root cause: {parser.format_frame(parser.extract_root_cause(frames))}")
