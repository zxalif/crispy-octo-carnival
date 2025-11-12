"""
LLM Cache utilities for generating cache keys.
"""

import hashlib
from typing import Optional

from core.logger import get_logger

logger = get_logger(__name__)


def generate_cache_key(text: str, cache_type: str = "classification") -> str:
    """
    Generate cache key from text content.
    
    Args:
        text: Text content to cache
        cache_type: Type of cache ("classification" or "info_extraction")
        
    Returns:
        SHA256 hash string (64 chars)
    """
    # Normalize text: lowercase, strip whitespace
    normalized = text.lower().strip()
    
    # Create cache key: hash of normalized text + cache type
    # This ensures same content always gets same cache key
    key_string = f"{cache_type}:{normalized}"
    cache_key = hashlib.sha256(key_string.encode('utf-8')).hexdigest()
    
    return cache_key

