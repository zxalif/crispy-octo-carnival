"""
Run the scheduler as a standalone service.
"""

import asyncio
import signal
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.config import get_config
from core.logger import get_logger, setup_logging
from core.env_validator import validate_and_exit
from modules.scheduler.scheduler import RixlyScheduler

logger = get_logger(__name__)


def signal_handler(sig, frame):
    """Handle shutdown signals."""
    logger.info("Received shutdown signal")
    sys.exit(0)


async def main():
    """Main scheduler loop."""
    # Validate environment variables before starting
    try:
        validate_and_exit(exit_on_error=True)
    except SystemExit:
        sys.exit(1)
    except Exception as e:
        logger.error("Environment validation error", error=str(e))
        sys.exit(1)
    
    # Get config (will also validate required fields)
    try:
        config = get_config()
    except ValueError as e:
        logger.error("Configuration error", error=str(e))
        sys.exit(1)
    
    # Setup logging (writes to both console and file)
    setup_logging(log_level=config.log_level, log_file=config.log_file)
    
    if not config.scheduler_enabled:
        logger.warning("Scheduler is disabled in config. Exiting.")
        return
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and start scheduler
    scheduler = RixlyScheduler()
    scheduler.start()
    
    logger.info("Scheduler service started. Press Ctrl+C to stop.")
    
    try:
        # Keep running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        scheduler.stop()
        logger.info("Scheduler service stopped")


if __name__ == "__main__":
    asyncio.run(main())

