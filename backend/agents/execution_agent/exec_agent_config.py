"""
Configuration Module
Centralized configuration for Execution Agent

Author: Accessibility AI Team
Version: 1.0.0
"""

import logging
from pathlib import Path
from enum import Enum


# ============================================================================
# ENUMS
# ============================================================================

class ExecutionContext(Enum):
    """Execution context types"""
    LOCAL = "local"
    WEB = "web"
    SYSTEM = "system"
    MOBILE = "mobile"
    HYBRID = "hybrid"


class ActionStatus(Enum):
    """Task execution status"""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    AWAITING_CONFIRMATION = "awaiting_confirmation"


class RiskLevel(Enum):
    """Risk assessment levels for Safety Layer"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FallbackStrategy(Enum):
    """Fallback strategies when primary method fails"""
    OCR = "ocr"
    COMPUTER_VISION = "computer_vision"
    KEYBOARD_SHORTCUT = "keyboard_shortcut"
    USER_GUIDANCE = "user_guidance"


# ============================================================================
# CONFIGURATION SETTINGS
# ============================================================================

class Config:
    """Central configuration class"""
    
    # Directories
    BASE_DIR = Path(__file__).parent
    LOG_DIR = BASE_DIR / "logs"
    SCREENSHOT_DIR = BASE_DIR / "screenshots"
    TEMPLATE_DIR = BASE_DIR / "templates"
    
    # Logging
    LOG_LEVEL = logging.INFO
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Execution Settings
    DEFAULT_TIMEOUT = 30
    DEFAULT_RETRY_COUNT = 3
    MAX_UNDO_HISTORY = 10
    
    # OCR Settings
    OCR_LANGUAGES = 'ara+eng'  # Arabic + English
    OCR_CONFIDENCE_THRESHOLD = 0.7
    
    # Computer Vision Settings
    CV_CONFIDENCE_THRESHOLD = 0.7
    
    # Action Layer Settings
    TYPE_INTERVAL = 0.05
    CLICK_DELAY = 0.5
    KEY_PRESS_DELAY = 0.3
    
    # Web Automation Settings
    WEB_WAIT_TIMEOUT = 10
    BROWSER_HEADLESS = False
    
    # Safety Settings
    RISK_RULES = {
        "delete": RiskLevel.HIGH,
        "send": RiskLevel.MEDIUM,
        "install": RiskLevel.CRITICAL,
        "download": RiskLevel.LOW,
        "click": RiskLevel.LOW,
        "type": RiskLevel.LOW,
        "execute": RiskLevel.HIGH,
        "modify": RiskLevel.MEDIUM,
        "format": RiskLevel.CRITICAL,
        "shutdown": RiskLevel.CRITICAL,
        "restart": RiskLevel.HIGH
    }
    
    @classmethod
    def create_directories(cls):
        """Create necessary directories"""
        cls.LOG_DIR.mkdir(exist_ok=True)
        cls.SCREENSHOT_DIR.mkdir(exist_ok=True)
        cls.TEMPLATE_DIR.mkdir(exist_ok=True)
    
    @classmethod
    def get_audit_file(cls):
        """Get audit log file path"""
        return cls.LOG_DIR / "audit.json"
