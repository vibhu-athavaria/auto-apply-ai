"""Structured logging for Worker service.

All logs must include:
- timestamp
- level
- service (worker)
- user_id (if applicable)
- action
- status

Never log:
- LinkedIn credentials
- Raw resumes
- Session cookies (unencrypted)
- LLM tokens
"""
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional

from config import settings


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured JSON-like logs."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured output."""
        # Base log data
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "service": "worker",
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields if present
        if hasattr(record, "extra") and record.extra:
            log_data.update(record.extra)

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Format as key=value pairs for readability
        parts = []
        for key, value in log_data.items():
            if isinstance(value, dict):
                # Flatten nested dicts
                for k, v in value.items():
                    parts.append(f"{k}={v}")
            else:
                parts.append(f"{key}={value}")

        return " ".join(parts)


class WorkerLogger(logging.Logger):
    """Custom logger with structured logging support."""

    def __init__(self, name: str, level: int = logging.NOTSET):
        super().__init__(name, level)

    def _log_with_extra(
        self,
        level: int,
        msg: str,
        args: tuple,
        exc_info: Any = None,
        extra: Optional[Dict[str, Any]] = None,
        stack_info: bool = False,
        stacklevel: int = 1
    ):
        """Log with extra fields."""
        # Create a new extra dict with our custom extra
        if extra:
            # Create a LogRecord-compatible extra dict
            record_extra = {"extra": extra}
        else:
            record_extra = {}

        super()._log(
            level, msg, args, exc_info, record_extra, stack_info, stacklevel
        )


def setup_logging():
    """Setup structured logging for the worker service."""
    # Set our custom logger class
    logging.setLoggerClass(WorkerLogger)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add stdout handler with structured formatter
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())
    root_logger.addHandler(handler)

    return root_logger


def get_logger(name: str) -> WorkerLogger:
    """Get a logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


# Initialize logging on module import
setup_logging()
