#!/usr/bin/env python3
"""
Create a new Alembic migration with autogenerate.
This script helps create migrations from model changes.
"""

import sys
import subprocess
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.config import get_config
from core.logger import setup_logging, get_logger


def create_migration(message: str):
    """
    Create a new Alembic migration using autogenerate.
    
    Args:
        message: Migration description message
    """
    logger = get_logger(__name__)
    config = get_config()
    
    # Setup logging
    setup_logging(log_level=config.log_level, log_file=config.log_file)
    
    logger.info("Creating new Alembic migration", message=message)
    
    # Run alembic revision with autogenerate
    try:
        result = subprocess.run(
            ["alembic", "revision", "--autogenerate", "-m", message],
            cwd=project_root,
            check=True
        )
        
        logger.info("Migration created successfully", message=message)
        print(f"\n✅ Migration created successfully!")
        print(f"   Message: {message}")
        print(f"\n📝 Next steps:")
        print(f"   1. Review the migration file in alembic/versions/")
        print(f"   2. Apply it: alembic upgrade head")
        print(f"   3. Or in Docker: docker-compose exec api alembic upgrade head")
        
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(
            "Failed to create migration",
            returncode=e.returncode,
            stderr=e.stderr if e.stderr else None
        )
        print(f"\n❌ Failed to create migration")
        print(f"   Error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error("Unexpected error", error=str(e))
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Create a new Alembic migration with autogenerate",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/create_migration.py "Add user table"
  python scripts/create_migration.py "Update lead schema"
        """
    )
    parser.add_argument(
        "message",
        help="Migration description message"
    )
    
    args = parser.parse_args()
    create_migration(args.message)

