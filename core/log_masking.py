"""
Log masking processor to prevent sensitive data from appearing in logs.
"""

import re
from typing import Any, Dict, List


# Patterns for sensitive data
SENSITIVE_PATTERNS = [
    # API Keys
    (r'(?i)(api[_-]?key["\']?\s*[:=]\s*["\']?)([^"\'\s,}]+)', r'\1***MASKED***'),
    (r'(?i)(apikey["\']?\s*[:=]\s*["\']?)([^"\'\s,}]+)', r'\1***MASKED***'),
    
    # Reddit credentials
    (r'(?i)(reddit[_-]?client[_-]?id["\']?\s*[:=]\s*["\']?)([^"\'\s,}]+)', r'\1***MASKED***'),
    (r'(?i)(reddit[_-]?client[_-]?secret["\']?\s*[:=]\s*["\']?)([^"\'\s,}]+)', r'\1***MASKED***'),
    
    # LLM API Keys
    (r'(?i)(groq[_-]?api[_-]?key["\']?\s*[:=]\s*["\']?)([^"\'\s,}]+)', r'\1***MASKED***'),
    (r'(?i)(openai[_-]?api[_-]?key["\']?\s*[:=]\s*["\']?)([^"\'\s,}]+)', r'\1***MASKED***'),
    
    # Database passwords
    (r'(?i)(password["\']?\s*[:=]\s*["\']?)([^"\'\s,}]+)', r'\1***MASKED***'),
    (r'(?i)(pwd["\']?\s*[:=]\s*["\']?)([^"\'\s,}]+)', r'\1***MASKED***'),
    (r'(?i)(pass["\']?\s*[:=]\s*["\']?)([^"\'\s,}]+)', r'\1***MASKED***'),
    
    # Database URLs with passwords
    (r'(postgresql://[^:]+:)([^@]+)(@)', r'\1***MASKED***\3'),
    (r'(mysql://[^:]+:)([^@]+)(@)', r'\1***MASKED***\3'),
    (r'(mongodb://[^:]+:)([^@]+)(@)', r'\1***MASKED***\3'),
    
    # Tokens
    (r'(?i)(token["\']?\s*[:=]\s*["\']?)([^"\'\s,}]+)', r'\1***MASKED***'),
    (r'(?i)(bearer\s+)([A-Za-z0-9\-._~+/]+)', r'\1***MASKED***'),
    
    # Secrets
    (r'(?i)(secret["\']?\s*[:=]\s*["\']?)([^"\'\s,}]+)', r'\1***MASKED***'),
    
    # Authorization headers
    (r'(?i)(authorization["\']?\s*[:=]\s*["\']?)([^"\'\s,}]+)', r'\1***MASKED***'),
    (r'(?i)(auth["\']?\s*[:=]\s*["\']?)([^"\'\s,}]+)', r'\1***MASKED***'),
]

# Keys that should be masked in dictionaries
SENSITIVE_KEYS = [
    'api_key', 'apikey', 'api-key',
    'reddit_client_id', 'reddit_client_secret', 'reddit-client-id', 'reddit-client-secret',
    'groq_api_key', 'groq-api-key', 'openai_api_key', 'openai-api-key',
    'password', 'pwd', 'pass', 'secret', 'token', 'auth', 'authorization',
    'database_password', 'database-password', 'db_password', 'db-password',
    'database_url', 'database-url', 'db_url', 'db-url',
]


def mask_string(text: str) -> str:
    """
    Mask sensitive data in a string.
    
    Args:
        text: Text to mask
        
    Returns:
        Masked text
    """
    if not isinstance(text, str):
        return text
    
    masked = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        masked = re.sub(pattern, replacement, masked)
    
    return masked


def mask_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mask sensitive data in a dictionary.
    
    Args:
        data: Dictionary to mask
        
    Returns:
        Masked dictionary
    """
    if not isinstance(data, dict):
        return data
    
    masked = {}
    for key, value in data.items():
        # Check if key is sensitive
        key_lower = key.lower().replace('_', '').replace('-', '')
        is_sensitive = any(
            sensitive_key.lower().replace('_', '').replace('-', '') in key_lower
            for sensitive_key in SENSITIVE_KEYS
        )
        
        if is_sensitive:
            # Mask the value
            if isinstance(value, str):
                masked[key] = "***MASKED***"
            elif isinstance(value, dict):
                masked[key] = mask_dict(value)
            elif isinstance(value, list):
                masked[key] = [mask_dict(item) if isinstance(item, dict) else "***MASKED***" if isinstance(item, str) else item for item in value]
            else:
                masked[key] = "***MASKED***"
        elif isinstance(value, dict):
            masked[key] = mask_dict(value)
        elif isinstance(value, list):
            masked[key] = [
                mask_dict(item) if isinstance(item, dict) else mask_string(item) if isinstance(item, str) else item
                for item in value
            ]
        elif isinstance(value, str):
            masked[key] = mask_string(value)
        else:
            masked[key] = value
    
    return masked


def mask_log_data(data: Any) -> Any:
    """
    Mask sensitive data in log data (handles dict, list, str, or other types).
    
    Args:
        data: Data to mask
        
    Returns:
        Masked data
    """
    if isinstance(data, dict):
        return mask_dict(data)
    elif isinstance(data, list):
        return [
            mask_log_data(item) for item in data
        ]
    elif isinstance(data, str):
        return mask_string(data)
    else:
        return data

