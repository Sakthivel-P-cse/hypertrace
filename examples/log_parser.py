# Log Parser - Extract errors and context from application logs
# Save as log_parser.py

import re
import logging
from datetime import datetime
from typing import List, Dict, Optional

logging.basicConfig(level=logging.INFO)

class LogParser:
    """Parse application logs to extract errors and relevant context"""
    
    def __init__(self):
        # Common log level patterns
        self.log_levels = ['ERROR', 'FATAL', 'CRITICAL', 'SEVERE', 'WARN', 'WARNING']
        
        # Common timestamp patterns
        self.timestamp_patterns = [
            r'\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}',  # ISO format
            r'\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2}',      # Apache format
            r'\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}',      # Syslog format
        ]
    
    def parse_logs(self, log_content: str) -> List[Dict]:
        """
        Parse log content and extract error entries
        
        Returns list of error entries with:
        - timestamp: when the error occurred
        - level: log level (ERROR, FATAL, etc.)
        - message: error message
        - logger: logger name/component
        - thread: thread ID (if available)
        - context: additional context lines
        """
        errors = []
        lines = log_content.split('\n')
        
        for i, line in enumerate(lines):
            # Check if line contains error level
            if not any(level in line.upper() for level in self.log_levels):
                continue
            
            error_entry = self._parse_log_line(line)
            if error_entry:
                # Add context (surrounding lines)
                context_before = lines[max(0, i-2):i]
                context_after = lines[i+1:min(len(lines), i+4)]
                
                error_entry['context_before'] = context_before
                error_entry['context_after'] = context_after
                error_entry['line_number'] = i + 1
                
                errors.append(error_entry)
        
        return errors
    
    def _parse_log_line(self, line: str) -> Optional[Dict]:
        """Parse a single log line"""
        entry = {}
        
        # Extract timestamp
        timestamp = self._extract_timestamp(line)
        if timestamp:
            entry['timestamp'] = timestamp
        
        # Extract log level
        level = self._extract_log_level(line)
        if level:
            entry['level'] = level
        
        # Extract logger/component name
        logger = self._extract_logger(line)
        if logger:
            entry['logger'] = logger
        
        # Extract thread ID
        thread = self._extract_thread_id(line)
        if thread:
            entry['thread'] = thread
        
        # Extract message (everything after level and metadata)
        entry['message'] = self._extract_message(line, level)
        entry['raw_line'] = line
        
        return entry if entry.get('level') else None
    
    def _extract_timestamp(self, line: str) -> Optional[str]:
        """Extract timestamp from log line"""
        for pattern in self.timestamp_patterns:
            match = re.search(pattern, line)
            if match:
                return match.group(0)
        return None
    
    def _extract_log_level(self, line: str) -> Optional[str]:
        """Extract log level"""
        for level in self.log_levels:
            if re.search(rf'\b{level}\b', line, re.IGNORECASE):
                return level
        return None
    
    def _extract_logger(self, line: str) -> Optional[str]:
        """Extract logger/component name"""
        # Common patterns for logger names
        patterns = [
            r'\[([a-zA-Z0-9_.-]+)\]',  # [LoggerName]
            r'<([a-zA-Z0-9_.-]+)>',    # <LoggerName>
            r'([a-zA-Z0-9_.-]+):\s*(?:ERROR|WARN|INFO)',  # LoggerName: ERROR
        ]
        
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_thread_id(self, line: str) -> Optional[str]:
        """Extract thread ID"""
        # Common thread patterns
        patterns = [
            r'\[thread-(\d+)\]',
            r'\[(\d+)\]',
            r'thread=(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_message(self, line: str, level: Optional[str]) -> str:
        """Extract error message"""
        if not level:
            return line
        
        # Find position after log level and extract rest as message
        match = re.search(rf'{level}\s*:?\s*(.+)', line, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        return line
    
    def extract_exception_name(self, log_entry: Dict) -> Optional[str]:
        """Extract exception name from log message"""
        message = log_entry.get('message', '')
        
        # Common exception patterns
        patterns = [
            r'([a-zA-Z0-9_]+(?:Exception|Error))',  # Java/Python exceptions
            r'([a-zA-Z0-9_]+Error)',                 # JavaScript errors
            r'System\.([a-zA-Z0-9_]+Exception)',     # C# exceptions
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message)
            if match:
                return match.group(1)
        
        return None
    
    def find_errors_by_service(self, log_content: str, service_name: str) -> List[Dict]:
        """Find errors related to a specific service"""
        all_errors = self.parse_logs(log_content)
        
        # Filter errors that mention the service
        service_errors = [
            error for error in all_errors
            if service_name.lower() in error.get('message', '').lower() or
               service_name.lower() in error.get('logger', '').lower()
        ]
        
        return service_errors
    
    def find_errors_in_timerange(self, errors: List[Dict], start_time: str, end_time: str) -> List[Dict]:
        """Filter errors within a time range"""
        filtered = []
        
        for error in errors:
            timestamp = error.get('timestamp')
            if not timestamp:
                continue
            
            # Simple string comparison (works for ISO format)
            if start_time <= timestamp <= end_time:
                filtered.append(error)
        
        return filtered
    
    def group_errors_by_type(self, errors: List[Dict]) -> Dict[str, List[Dict]]:
        """Group errors by exception type"""
        grouped = {}
        
        for error in errors:
            exception_name = self.extract_exception_name(error) or 'Unknown'
            
            if exception_name not in grouped:
                grouped[exception_name] = []
            
            grouped[exception_name].append(error)
        
        return grouped
    
    def get_error_frequency(self, errors: List[Dict]) -> Dict[str, int]:
        """Count frequency of each error type"""
        grouped = self.group_errors_by_type(errors)
        return {error_type: len(entries) for error_type, entries in grouped.items()}


# Example usage and testing
if __name__ == "__main__":
    parser = LogParser()
    
    # Test log content
    sample_logs = """
2026-01-01 10:00:15 [payment-service] INFO: Processing payment request
2026-01-01 10:00:16 [payment-service] ERROR: NullPointerException in PaymentService.processPayment
2026-01-01 10:00:16 [payment-service] ERROR: at com.example.payment.PaymentService.processPayment(PaymentService.java:42)
2026-01-01 10:00:17 [db-service] WARN: Connection pool running low
2026-01-01 10:00:18 [payment-service] FATAL: Unable to connect to database
2026-01-01 10:00:19 [api-gateway] ERROR: Timeout waiting for payment-service response
    """
    
    print("Parsing logs...")
    errors = parser.parse_logs(sample_logs)
    
    print(f"\nFound {len(errors)} errors:\n")
    for error in errors:
        print(f"[{error.get('timestamp')}] {error.get('level')} - {error.get('logger')}")
        print(f"  Message: {error.get('message')}")
        exception = parser.extract_exception_name(error)
        if exception:
            print(f"  Exception: {exception}")
        print()
    
    # Group by type
    print("Error frequency:")
    frequency = parser.get_error_frequency(errors)
    for error_type, count in frequency.items():
        print(f"  {error_type}: {count}")
