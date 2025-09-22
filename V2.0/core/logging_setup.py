"""
Logging Setup for Scanner System

Provides centralized logging configuration with multiple output formats,
log rotation, and module-specific logging levels.

Author: Scanner System Development
Created: September 2025
"""

import logging
import logging.handlers
import sys
import os
from pathlib import Path
from typing import Optional, Union
from datetime import datetime


class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colors to log levels for console output"""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[1;31m' # Bold Red
    }
    RESET = '\033[0m'
    
    def format(self, record):
        # Add color to the level name
        if record.levelname in self.COLORS:
            record.levelname = (
                f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"
            )
        return super().format(record)


class ScannerLogFilter(logging.Filter):
    """Custom filter for scanner-specific log formatting"""
    
    def filter(self, record):
        # Add scanner module information if not present
        if not hasattr(record, 'scanner_module'):
            # Extract module from logger name
            name_parts = record.name.split('.')
            if len(name_parts) >= 2:
                record.scanner_module = name_parts[1]  # e.g., 'motion', 'camera', etc.
            else:
                record.scanner_module = 'system'
        
        return True


def setup_logging(log_level: str = "INFO", 
                 log_dir: Optional[Path] = None,
                 enable_console: bool = True,
                 enable_file: bool = True,
                 max_file_size: int = 10 * 1024 * 1024,  # 10MB
                 backup_count: int = 5) -> logging.Logger:
    """
    Setup centralized logging for the scanner system
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files (None for default)
        enable_console: Enable console logging
        enable_file: Enable file logging
        max_file_size: Maximum log file size before rotation
        backup_count: Number of backup log files to keep
        
    Returns:
        Configured root logger
    """
    
    # Convert string level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Create log directory
    if log_dir is None:
        log_dir = Path.home() / "scanner_logs"
    
    log_dir = Path(log_dir)
    log_dir.mkdir(exist_ok=True)
    
    # Clear any existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Set root logger level
    root_logger.setLevel(numeric_level)
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(scanner_module)-8s | %(name)-20s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_formatter = ColoredFormatter(
        fmt='%(asctime)s | %(levelname)-8s | %(scanner_module)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Setup console handler
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(console_formatter)
        console_handler.addFilter(ScannerLogFilter())
        root_logger.addHandler(console_handler)
    
    # Setup rotating file handler for main log
    if enable_file:
        main_log_file = log_dir / "scanner_system.log"
        file_handler = logging.handlers.RotatingFileHandler(
            filename=main_log_file,
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(detailed_formatter)
        file_handler.addFilter(ScannerLogFilter())
        root_logger.addHandler(file_handler)
        
        # Setup separate error log
        error_log_file = log_dir / "scanner_errors.log"
        error_handler = logging.handlers.RotatingFileHandler(
            filename=error_log_file,
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_formatter)
        error_handler.addFilter(ScannerLogFilter())
        root_logger.addHandler(error_handler)
    
    # Configure module-specific loggers
    _configure_module_loggers(log_dir, detailed_formatter, numeric_level, enable_file)
    
    # Log startup information
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("Scanner System Logging Initialized")
    logger.info(f"Log Level: {log_level}")
    logger.info(f"Log Directory: {log_dir}")
    logger.info(f"Console Logging: {enable_console}")
    logger.info(f"File Logging: {enable_file}")
    logger.info("=" * 60)
    
    return root_logger


def _configure_module_loggers(log_dir: Path, formatter: logging.Formatter, 
                            level: int, enable_file: bool):
    """Configure specialized loggers for different modules"""
    
    module_configs = [
        ('motion', 'motion_control.log'),
        ('camera', 'camera_control.log'),
        ('lighting', 'led_control.log'),
        ('planning', 'path_planning.log'),
        ('storage', 'data_storage.log'),
        ('web', 'web_interface.log'),
        ('communication', 'data_transfer.log'),
        ('orchestration', 'scan_coordination.log')
    ]
    
    if enable_file:
        for module_name, log_filename in module_configs:
            logger = logging.getLogger(module_name)
            
            # Create dedicated file handler for this module
            module_log_file = log_dir / log_filename
            module_handler = logging.handlers.RotatingFileHandler(
                filename=module_log_file,
                maxBytes=5 * 1024 * 1024,  # 5MB per module
                backupCount=3,
                encoding='utf-8'
            )
            module_handler.setLevel(level)
            module_handler.setFormatter(formatter)
            
            # Add filter to only log messages from this module
            module_handler.addFilter(ModuleFilter(module_name))
            logger.addHandler(module_handler)


class ModuleFilter(logging.Filter):
    """Filter to only allow logs from a specific module"""
    
    def __init__(self, module_name: str):
        super().__init__()
        self.module_name = module_name
    
    def filter(self, record):
        return record.name.startswith(self.module_name)


def get_logger(name: str, module: Optional[str] = None) -> Union[logging.Logger, logging.LoggerAdapter]:
    """
    Get a logger for a specific component
    
    Args:
        name: Logger name
        module: Module name (motion, camera, etc.)
        
    Returns:
        Configured logger
    """
    if module:
        logger_name = f"{module}.{name}"
    else:
        logger_name = name
    
    logger = logging.getLogger(logger_name)
    
    # Add module attribute for filtering
    class ModuleLoggerAdapter(logging.LoggerAdapter):
        def process(self, msg, kwargs):
            if module:
                kwargs.setdefault('extra', {})['module'] = module
            return msg, kwargs
    
    return ModuleLoggerAdapter(logger, {}) if module else logger


def log_system_info():
    """Log system information for debugging"""
    logger = get_logger('system_info', 'system')
    
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Platform: {sys.platform}")
    logger.info(f"Working directory: {os.getcwd()}")
    logger.info(f"Process ID: {os.getpid()}")
    
    # Log environment variables related to the scanner
    scanner_env_vars = [
        'SCANNER_DEBUG', 'SCANNER_SIMULATION', 'SCANNER_LOG_LEVEL',
        'FLUIDNC_PORT', 'WEB_PORT', 'LED_GPIO_1', 'LED_GPIO_2'
    ]
    
    for env_var in scanner_env_vars:
        value = os.getenv(env_var)
        if value:
            logger.info(f"Environment: {env_var}={value}")


def create_session_logger(session_id: str, log_dir: Optional[Path] = None) -> logging.Logger:
    """
    Create a dedicated logger for a scan session
    
    Args:
        session_id: Unique session identifier
        log_dir: Directory for session logs
        
    Returns:
        Session-specific logger
    """
    if log_dir is None:
        log_dir = Path.home() / "scanner_logs" / "sessions"
    
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Create session logger
    logger_name = f"session.{session_id}"
    session_logger = logging.getLogger(logger_name)
    
    # Prevent adding multiple handlers to the same logger
    if session_logger.handlers:
        return session_logger
    
    session_logger.setLevel(logging.DEBUG)
    
    # Session log file
    session_log_file = log_dir / f"session_{session_id}.log"
    session_handler = logging.FileHandler(session_log_file, encoding='utf-8')
    
    session_formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    session_handler.setFormatter(session_formatter)
    session_logger.addHandler(session_handler)
    
    session_logger.info(f"Session logging started: {session_id}")
    session_logger.info(f"Session log file: {session_log_file}")
    
    return session_logger


def cleanup_old_logs(log_dir: Optional[Path] = None, days_to_keep: int = 30):
    """
    Clean up old log files
    
    Args:
        log_dir: Directory containing log files
        days_to_keep: Number of days of logs to keep
    """
    if log_dir is None:
        log_dir = Path.home() / "scanner_logs"
    
    log_dir = Path(log_dir)
    
    if not log_dir.exists():
        return
    
    cutoff_time = datetime.now().timestamp() - (days_to_keep * 24 * 60 * 60)
    
    for log_file in log_dir.rglob("*.log*"):
        try:
            if log_file.stat().st_mtime < cutoff_time:
                log_file.unlink()
                print(f"Deleted old log file: {log_file}")
        except Exception as e:
            print(f"Failed to delete log file {log_file}: {e}")


# Convenience function for quick logger setup during development
def setup_simple_logging(level: str = "INFO") -> logging.Logger:
    """Setup simple console-only logging for development/testing"""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%H:%M:%S'
    )
    return logging.getLogger()