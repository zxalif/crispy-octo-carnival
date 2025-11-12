"""
Centralized Logging Configuration for Rixly.

Provides structured logging with log rotation, console and file output,
and automatic sensitive data masking.
"""

import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from logging.handlers import RotatingFileHandler

import structlog

from core.log_masking import mask_log_data


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    enable_file_logging: bool = True
) -> None:
    """
    Configure centralized structured logging for the application.
    
    Features:
    - Console output (stdout) with structured formatting
    - File output with log rotation (10MB max, 5 backups)
    - Automatic sensitive data masking
    - Structured logging via structlog
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file (defaults to logs/app.log)
        enable_file_logging: Whether to enable file logging (default: True)
    """
    # Default log file if not provided
    if log_file is None:
        log_file = "logs/app.log"
    
    # Create logs directory if it doesn't exist
    if enable_file_logging:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Get root logger
    root_logger = logging.getLogger()
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)
    
    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    # Console handler (stdout) - always enabled
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_formatter = logging.Formatter("%(message)s")
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler with rotation - if enabled
    if enable_file_logging:
        try:
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,  # Keep 5 backup files
                encoding='utf-8'
            )
            file_handler.setLevel(numeric_level)
            # More detailed format for file logs
            file_formatter = logging.Formatter(
                "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)
            
            # Log that file logging is enabled (use basic logging to avoid circular dependency)
            root_logger.info(f"Logging to file: {log_file} (rotation: 10MB, 5 backups)")
        except Exception as e:
            # If file logging fails, continue with console only
            root_logger.warning(f"Failed to setup file logging: {e}")
    
    # Set levels for third-party loggers
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    
    # Custom processor to mask sensitive data
    def mask_sensitive_data(logger, method_name, event_dict):
        """Mask sensitive data in log events."""
        # Mask values in event_dict
        masked_dict = mask_log_data(event_dict)
        return masked_dict
    
    # Configure structlog to use standard logging
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.format_exc_info,
            mask_sensitive_data,  # Add masking processor
            structlog.dev.ConsoleRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Get a logger instance.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured logger instance
    """
    return structlog.get_logger(name)

