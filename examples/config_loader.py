"""
Configuration utility for loading settings from environment variables and YAML files.
Handles environment variable substitution in YAML configs.
"""

import os
import re
import yaml
from typing import Any, Dict, Optional
from pathlib import Path


def expand_env_vars(value: Any) -> Any:
    """
    Recursively expand environment variables in configuration values.
    
    Supports syntax: ${VAR_NAME} or ${VAR_NAME:-default_value}
    
    Examples:
        "${NEO4J_PASSWORD}" -> reads NEO4J_PASSWORD env var
        "${NEO4J_PASSWORD:-password}" -> reads NEO4J_PASSWORD or defaults to 'password'
    """
    if isinstance(value, str):
        # Pattern: ${VAR_NAME} or ${VAR_NAME:-default}
        pattern = r'\$\{([^}:]+)(?::([^}]+))?\}'
        
        def replacer(match):
            var_name = match.group(1)
            default_value = match.group(2) if match.group(2) else ''
            # Remove leading '-' from default value if present
            if default_value.startswith('-'):
                default_value = default_value[1:]
            return os.getenv(var_name, default_value)
        
        return re.sub(pattern, replacer, value)
    
    elif isinstance(value, dict):
        return {k: expand_env_vars(v) for k, v in value.items()}
    
    elif isinstance(value, list):
        return [expand_env_vars(item) for item in value]
    
    return value


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load YAML configuration file with environment variable expansion.
    
    Args:
        config_path: Path to YAML configuration file
    
    Returns:
        Dictionary with configuration values, environment variables expanded
    
    Example:
        config = load_config('examples/rca_config.yaml')
        neo4j_password = config['neo4j']['password']  # Will read from NEO4J_PASSWORD env var
    """
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    
    # Expand environment variables
    config = expand_env_vars(config)
    
    return config


def get_env(var_name: str, default: Optional[str] = None, required: bool = False) -> str:
    """
    Get environment variable with optional default and required check.
    
    Args:
        var_name: Name of environment variable
        default: Default value if not set
        required: If True, raises ValueError if not set and no default
    
    Returns:
        Environment variable value
    
    Raises:
        ValueError: If required=True and variable is not set
    """
    value = os.getenv(var_name, default)
    
    if required and not value:
        raise ValueError(
            f"Required environment variable '{var_name}' is not set. "
            f"Please set it in your environment or .env file."
        )
    
    return value


def load_env_file(env_file: str = '.env'):
    """
    Load environment variables from a .env file.
    
    Args:
        env_file: Path to .env file (default: '.env' in current directory)
    
    Note:
        This is a simple implementation. For production, consider using python-dotenv package.
    """
    env_path = Path(env_file)
    
    if not env_path.exists():
        return
    
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            
            # Parse KEY=VALUE
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                
                # Only set if not already in environment
                if key not in os.environ:
                    os.environ[key] = value


# Convenience function to initialize configuration at module import
def init_config(env_file: str = '.env'):
    """
    Initialize configuration by loading .env file.
    
    Call this at the start of your application:
        from config_loader import init_config
        init_config()
    """
    # Try to load .env from current directory
    load_env_file(env_file)
    
    # Also try to load from parent directory (for examples/ subdirectory)
    parent_env = Path('..') / env_file
    if parent_env.exists():
        load_env_file(str(parent_env))


# Auto-initialize when module is imported
# This will look for .env file and load it
if os.path.exists('.env'):
    load_env_file('.env')
elif os.path.exists('../.env'):
    load_env_file('../.env')


if __name__ == '__main__':
    # Test the configuration loader
    print("Testing configuration loader...")
    
    # Set some test environment variables
    os.environ['TEST_VAR'] = 'test_value'
    os.environ['NEO4J_PASSWORD'] = 'secret123'
    
    # Test expand_env_vars
    test_config = {
        'database': {
            'password': '${NEO4J_PASSWORD}',
            'host': '${DB_HOST:-localhost}',
            'port': '${DB_PORT:-7687}'
        },
        'api_key': '${API_KEY:-default_key}'
    }
    
    expanded = expand_env_vars(test_config)
    print("Expanded config:")
    print(expanded)
    
    # Expected output:
    # {
    #   'database': {
    #     'password': 'secret123',
    #     'host': 'localhost',
    #     'port': '7687'
    #   },
    #   'api_key': 'default_key'
    # }
