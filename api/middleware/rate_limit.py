"""
Rate limiting middleware using slowapi with Redis support.
"""

import os
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request

from core.config import get_config
from core.logger import get_logger

logger = get_logger(__name__)
config = get_config()

# Determine storage URI (Redis if available, otherwise memory)
def get_storage_uri() -> str:
    """Get Redis storage URI or fallback to memory."""
    redis_host = getattr(config, 'redis_host', None) or os.getenv('REDIS_HOST', 'localhost')
    redis_port = getattr(config, 'redis_port', None) or int(os.getenv('REDIS_PORT', '6379'))
    redis_db = getattr(config, 'redis_db', None) or int(os.getenv('REDIS_DB', '0'))
    redis_password = getattr(config, 'redis_password', None) or os.getenv('REDIS_PASSWORD', '')
    
    # Try to use Redis if host is configured (localhost works with host network mode)
    if redis_host and redis_host.strip():
        # Build Redis URI
        if redis_password:
            storage_uri = f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}"
        else:
            storage_uri = f"redis://{redis_host}:{redis_port}/{redis_db}"
        
        # Test Redis connection (optional, but helpful for logging)
        try:
            import redis
            r = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                password=redis_password if redis_password else None,
                socket_connect_timeout=2,
                decode_responses=False
            )
            r.ping()
            logger.info("Using Redis for rate limiting", host=redis_host, port=redis_port)
            return storage_uri
        except ImportError:
            logger.warning(
                "Redis module not installed, falling back to memory storage. "
                "Install redis package for Redis support."
            )
            return "memory://"
        except Exception as e:
            logger.warning(
                "Redis connection failed, falling back to memory storage",
                error=str(e),
                host=redis_host
            )
            return "memory://"
    else:
        # Use memory storage as fallback
        logger.info("Using in-memory storage for rate limiting")
        return "memory://"

# Initialize rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["1000/hour", "100/minute"],  # Default limits
    storage_uri=get_storage_uri()
)

# Custom rate limit exceeded handler
def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Custom handler for rate limit exceeded."""
    logger.warning(
        "Rate limit exceeded",
        path=request.url.path,
        ip=get_remote_address(request)
    )
    from fastapi.responses import JSONResponse
    from fastapi import status
    
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "error": {
                "message": "Rate limit exceeded. Please try again later.",
                "error_code": "rate_limit_exceeded",
                "retry_after": exc.retry_after
            }
        },
        headers={"Retry-After": str(exc.retry_after)}
    )

