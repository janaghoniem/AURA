"""
Logging Module
Centralized logging setup for Execution Agent

Author: Accessibility AI Team
Version: 1.0.0
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from exec_agent_config import Config


def setup_logging(name="ExecutionAgent", log_level=None):
    """
    Configure logging for Execution Agent
    
    Args:
        name: Logger name
        log_level: Logging level (default from Config)
    
    Returns:
        Logger instance
    """
    if log_level is None:
        log_level = Config.LOG_LEVEL
    
    # Create log directory
    Config.LOG_DIR.mkdir(exist_ok=True)
    
    # Log file with date
    log_file = Config.LOG_DIR / f"{name.lower()}_{datetime.now().strftime('%Y%m%d')}.log"
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    # Clear existing handlers
    if logger.handlers:
        logger.handlers.clear()
    
    # File handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(Config.LOG_FORMAT))
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter(Config.LOG_FORMAT))
    
    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger
