#!/usr/bin/env python3
"""
Run Alembic migrations automatically.
This script is called during Docker container startup.
"""

import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.config import get_config
from core.logger import setup_logging, get_logger
from modules.database.storage import LeadStorage


def wait_for_database(max_retries: int = 30, retry_delay: int = 2):
    """
    Wait for database to be ready.
    
    Args:
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds
    """
    logger = get_logger(__name__)
    
    for attempt in range(1, max_retries + 1):
        try:
            storage = LeadStorage()
            # Try to connect
            storage.get_session().close()
            logger.info("Database is ready")
            return True
        except Exception as e:
            if attempt < max_retries:
                logger.info(
                    f"Waiting for database... (attempt {attempt}/{max_retries})",
                    error=str(e)
                )
                time.sleep(retry_delay)
            else:
                logger.error("Database connection failed after all retries", error=str(e))
                return False
    
    return False


def run_migrations():
    """Run Alembic migrations."""
    import subprocess
    import os
    
    logger = get_logger(__name__)
    config = get_config()
    
    # Setup logging
    setup_logging(log_level=config.log_level, log_file=config.log_file)
    
    logger.info("Starting database migrations")
    
    # Wait for database to be ready
    if not wait_for_database():
        logger.error("Database is not ready. Exiting.")
        sys.exit(1)
    
    # Ensure DATABASE_URL is set for Alembic
    # Alembic reads from alembic.ini or environment
    if config.database_url:
        os.environ["DATABASE_URL"] = config.database_url
    else:
        os.environ["DATABASE_URL"] = config.database_url_from_parts
    
    logger.info("Database URL configured for migrations")
    
    # Run migrations
    try:
        logger.info("Running Alembic migrations...")
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True
        )
        
        logger.info("Migrations completed successfully")
        if result.stdout:
            # Log migration output (but mask sensitive data)
            output_lines = result.stdout.strip().split('\n')
            for line in output_lines:
                if line.strip():
                    logger.info("Migration", message=line)
        
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(
            "Migration failed",
            returncode=e.returncode,
            stdout=e.stdout if e.stdout else None,
            stderr=e.stderr if e.stderr else None
        )
        sys.exit(1)
    except Exception as e:
        logger.error("Unexpected error during migrations", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    run_migrations()

