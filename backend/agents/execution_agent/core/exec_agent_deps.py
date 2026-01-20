"""
Dependencies Module
Check and manage external dependencies

Author: Accessibility AI Team
Version: 1.0.0
"""

# Stub classes for missing dependencies
class _StubClass:
    """Placeholder for unavailable dependencies"""
    def __init__(self, *args, **kwargs):
        raise RuntimeError(f"{self.__class__.__name__} is not available. Install the required package.")

# Check for optional dependencies
try:
    import pywinauto
    from pywinauto import Application, Desktop
    from pywinauto.controls.uiawrapper import UIAWrapper
    PYWINAUTO_AVAILABLE = True
except ImportError:
    PYWINAUTO_AVAILABLE = False
    Application = _StubClass
    Desktop = _StubClass
    UIAWrapper = _StubClass

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    pyautogui = None

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    webdriver = None
    By = _StubClass
    WebDriverWait = _StubClass
    EC = _StubClass

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    sync_playwright = None

try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    pytesseract = None
    Image = None


def check_dependencies(logger):
    """
    Check and log available automation libraries
    
    Args:
        logger: Logger instance
    
    Returns:
        dict: Dictionary of dependency statuses
    """
    deps = {
        "PyWinAuto": PYWINAUTO_AVAILABLE,
        "PyAutoGUI": PYAUTOGUI_AVAILABLE,
        "Selenium": SELENIUM_AVAILABLE,
        "Playwright": PLAYWRIGHT_AVAILABLE,
        "OCR (Tesseract)": OCR_AVAILABLE
    }
    
    logger.info("Checking dependencies:")
    for dep, available in deps.items():
        status = "[OK]" if available else "[MISSING]"
        logger.info(f"  {status} {dep}")
    
    return deps


def get_missing_dependencies():
    """
    Get list of missing dependencies
    
    Returns:
        list: List of missing dependency names
    """
    missing = []
    
    if not PYWINAUTO_AVAILABLE:
        missing.append("pywinauto")
    if not PYAUTOGUI_AVAILABLE:
        missing.append("pyautogui")
    if not SELENIUM_AVAILABLE:
        missing.append("selenium")
    if not PLAYWRIGHT_AVAILABLE:
        missing.append("playwright")
    if not OCR_AVAILABLE:
        missing.append("pytesseract and Pillow")
    
    return missing
