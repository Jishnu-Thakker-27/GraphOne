"""
Logging and General Helpers.

Configures unified logging with support for both human-readable
colored console logs and structured JSON logs for production deployments.
"""

import sys
import json
from loguru import logger
from src.config.config import settings

def json_formatter(record) -> str:
    """Formats loguru records into structured JSON lines."""
    log_dict = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "message": record["message"],
        "module": record["module"],
        "function": record["function"],
        "line": record["line"],
    }
    if record["exception"]:
        log_dict["exception"] = {
            "type": str(record["exception"].type),
            "value": str(record["exception"].value),
            "traceback": record["exception"].traceback is not None
        }
    # Return formatted string with format parameter placeholder
    return json.dumps(log_dict) + "\n"

def setup_logging() -> None:
    """Configures centralized loguru handlers according to system settings."""
    logger.remove()  # Remove default console handler
    
    log_level = settings.LOG_LEVEL.upper()
    
    if settings.ENABLE_JSON_LOGGING:
        # Use lambda formatting wrapper for loguru handler
        logger.add(
            sys.stdout,
            level=log_level,
            format=lambda r: json_formatter(r),
            colorize=False
        )
    else:
        logger.add(
            sys.stdout,
            level=log_level,
            format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            colorize=True
        )
