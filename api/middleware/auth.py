"""
Simple API key authentication middleware.
"""

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from core.config import get_config

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """
    Verify API key from header.
    
    Args:
        api_key: API key from header
        
    Returns:
        API key if valid
        
    Raises:
        HTTPException if invalid
    """
    config = get_config()
    expected_key = getattr(config, "api_key", None)
    
    # If no API key configured, allow all requests (development mode)
    if not expected_key:
        return "dev_key"
    
    if not api_key or api_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )
    
    return api_key

