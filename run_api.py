"""
Run the Rixly API server.
"""

import sys
import uvicorn
from core.config import get_config
from core.env_validator import validate_and_exit

if __name__ == "__main__":
    # Validate environment variables before starting
    try:
        validate_and_exit(exit_on_error=True)
    except SystemExit:
        sys.exit(1)
    except Exception as e:
        print(f"❌ Environment validation error: {e}")
        sys.exit(1)
    
    # Get config (will also validate required fields)
    try:
        config = get_config()
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        sys.exit(1)
    
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=not config.is_production,  # Enable reload in development
        reload_dirs=["/app"] if not config.is_production else [],  # Watch entire app directory
        reload_includes=["*.py"],  # Watch Python files
        log_level=config.log_level.lower()
    )

