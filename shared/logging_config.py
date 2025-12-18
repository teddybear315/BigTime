"""
Centralized logging configuration for BigTime application.
Provides consistent logging across client and server components.
"""

import logging
import sys
from datetime import datetime

try:
    from termcolor import colored
except ImportError:
    # Fallback if termcolor not available
    def colored(text, color=None, on_color=None, attrs=None):
        return text

from shared.utils import get_data_path


class BigTimeFormatter(logging.Formatter):
    """Custom formatter with component identification and colors for console"""

    # Color mapping for different log levels
    LEVEL_COLORS = {
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'magenta'
    }

    def __init__(self, component: str, use_colors: bool = True):
        self.component = component
        # Handle case where sys.stdout is None (PyInstaller builds)
        try:
            self.use_colors = use_colors and sys.stdout and sys.stdout.isatty()
        except (AttributeError, OSError):
            self.use_colors = False

        # Format: [TIMESTAMP] [COMPONENT] [LEVEL] Message
        super().__init__(
            fmt='[%(asctime)s] [%(component)s] [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    def format(self, record):
        # Add component to record
        record.component = self.component

        # Format the message first
        formatted = super().format(record)

        # Apply colors if enabled
        if self.use_colors:
            try:
                color = self.LEVEL_COLORS.get(record.levelname, 'white')
                return colored(formatted, color)
            except (ImportError, AttributeError):
                # Fallback if termcolor is not available
                return formatted
        else:
            return formatted


def setup_logging(component: str, level: str = "INFO", log_to_file: bool = True) -> logging.Logger:
    """Setup standardized logging for BigTime components.

    Configures console and optional file logging with consistent formatting.
    Handles edge cases where stdout/stderr may be unavailable (PyInstaller builds).

    Args:
        component: Component name (e.g., 'CLIENT', 'SERVER', 'SYNC') for logger identification
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL). Defaults to INFO
        log_to_file: Whether to also log to file in logs/ directory. Defaults to True

    Returns:
        Configured logger instance with console and optional file handlers

    Note:
        Prevents duplicate handlers if called multiple times with same component.
    """
    logger = logging.getLogger(f"bigtime.{component.lower()}")

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Console handler with colors
    # Handle case where sys.stdout is None (PyInstaller builds)
    try:
        if sys.stdout:
            console_handler = logging.StreamHandler(sys.stdout)
        else:
            # Use stderr as fallback, or default StreamHandler if both are None
            console_handler = logging.StreamHandler(sys.stderr or None)
        console_handler.setFormatter(BigTimeFormatter(component, use_colors=True))
        logger.addHandler(console_handler)
    except (AttributeError, OSError):
        # Fallback to basic StreamHandler without explicit stream
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(BigTimeFormatter(component, use_colors=False))
        logger.addHandler(console_handler)

    # File handler if requested
    if log_to_file:
        try:
            log_dir = get_data_path('logs')
            log_dir.mkdir(exist_ok=True)

            log_file = log_dir / f"bigtime_{component.lower()}_{datetime.now().strftime('%m-%d-%Y %H-%M-%S')}.log"

            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(BigTimeFormatter(component, use_colors=False))
            logger.addHandler(file_handler)

        except Exception as e:
            # If file logging fails, just log to console
            logger.warning(f"Could not setup file logging: {e}")

    return logger


def get_logger(component: str) -> logging.Logger:
    """Get existing logger for component or create with default settings"""
    logger_name = f"bigtime.{component.lower()}"

    # Return existing logger if it exists
    existing = logging.getLogger(logger_name)
    if existing.handlers:
        return existing

    # Create new logger with default settings
    return setup_logging(component)


# Convenience functions for common components
def get_client_logger() -> logging.Logger:
    """Get logger for client components"""
    return get_logger("CLIENT")


def get_server_logger() -> logging.Logger:
    """Get logger for server components"""
    return get_logger("SERVER")


def get_sync_logger() -> logging.Logger:
    """Get logger for sync operations"""
    return get_logger("SYNC")


def set_log_level(level: str):
    """Set log level for all BigTime loggers"""
    level_obj = getattr(logging, level.upper(), logging.INFO)

    for name in logging.root.manager.loggerDict:
        if name.startswith('bigtime.'):
            logger = logging.getLogger(name)
            logger.setLevel(level_obj)

            # Also update handler levels
            for handler in logger.handlers:
                handler.setLevel(level_obj)


def enable_debug_logging():
    """Enable debug logging for troubleshooting"""
    set_log_level("DEBUG")


def disable_debug_logging():
    """Disable debug logging for production"""
    set_log_level("INFO")
