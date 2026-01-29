"""
Vision Layer Module
Handles screen perception: OCR, element detection, layout understanding

Author: Accessibility AI Team
Version: 1.0.0
"""

import time
from datetime import datetime
from typing import Dict, Optional
from pathlib import Path

# from backend.agents.execution_agent.core.exec_agent_config import Config
# from backend.agents.execution_agent.core.exec_agent_models import VisionResult
# from backend.agents.execution_agent.core.exec_agent_deps import (
#     PYWINAUTO_AVAILABLE, PYAUTOGUI_AVAILABLE, OCR_AVAILABLE,
#     pyautogui, pytesseract, Image
# )
from ..core.exec_agent_config import Config
from ..core.exec_agent_models import VisionResult
from ..core.exec_agent_deps import PYWINAUTO_AVAILABLE, PYAUTOGUI_AVAILABLE, OCR_AVAILABLE, pyautogui, pytesseract, Image
from ..fallback import OmniParserDetector, OMNIPARSER_AVAILABLE
# Add after other imports
try:
    from ..fallback import OmniParserDetector, OMNIPARSER_AVAILABLE
    OMNIPARSER_AVAILABLE = True
except ImportError as e:
    OMNIPARSER_AVAILABLE = False
    OmniParserDetector = None

class VisionLayer:
    """
    Handles screen perception: OCR, element detection, layout understanding
    """
    
    def __init__(self, logger):
        self.logger = logger
        self.screenshot_dir = Config.SCREENSHOT_DIR
        self.screenshot_dir.mkdir(exist_ok=True)

        #by shahd for the fallback :)
        self.omniparser = None
        if OMNIPARSER_AVAILABLE and OmniParserDetector is not None:
            try: 
                self.omniparser_detector = OmniParserDetector(logger)
                self.logger.info("✅ OmniParserDetector fallback available")
            except Exception as e:
                self.logger.error(f"❌ Failed to initialize OmniParserDetector: {e}")
                self.omniparser = None
        else:
            self.logger.info("⚠️ OmniParserDetector fallback NOT available")


    def detect_element_omniparser(self, target_text: str) -> VisionResult:
        """
        Detect element using OmniParser (Advanced AI fallback)
        Use when UIA, OCR, and CV all fail
        
        Args:
            target_text: Description of element to find
        
        Returns:
            VisionResult
        """
        if not OMNIPARSER_AVAILABLE or self.omniparser is None:
            return VisionResult(False, None, 0.0, None, "omniparser_unavailable")
        
        try:
            # Capture fresh screenshot
            screenshot_path = self.capture_screen()
            if not screenshot_path:
                return VisionResult(False, None, 0.0, None, "omniparser_screenshot_failed")
            
            # Use OmniParser to detect
            result = self.omniparser.detect_element_by_text(target_text, screenshot_path)
            
            return result
        
        except Exception as e:
            self.logger.error(f"OmniParser detection error: {e}")
            return VisionResult(False, None, 0.0, None, f"omniparser_error: {e}")


        #done, with regards, shahd :)
    def capture_screen(self, region=None) -> Optional[str]:
        """
        Capture screenshot of screen or specific region
        
        Args:
            region: Optional tuple (x, y, width, height)
        
        Returns:
            Screenshot file path or None
        """
        if not PYAUTOGUI_AVAILABLE:
            self.logger.warning("PyAutoGUI not available for screen capture")
            return None
        
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            screenshot_path = self.screenshot_dir / f"screen_{timestamp}.png"
            
            if region:
                screenshot = pyautogui.screenshot(region=region)
            else:
                screenshot = pyautogui.screenshot()
            
            screenshot.save(screenshot_path)
            self.logger.info(f"Screenshot saved: {screenshot_path}")
            return str(screenshot_path)
        
        except Exception as e:
            self.logger.error(f"Screen capture failed: {e}")
            return None
    
    def detect_element_uia(self, window, element_description: Dict) -> VisionResult:
        """
        Detect element using Windows UI Automation
        Priority method: most reliable for accessible apps
        
        Args:
            window: PyWinAuto window object
            element_description: Dict with selectors (auto_id, title, control_type, etc.)
        
        Returns:
            VisionResult
        """
        if not PYWINAUTO_AVAILABLE:
            return VisionResult(False, None, 0.0, None, "uia_unavailable")
        
        try:
            # Try multiple UIA selectors
            selectors = [
                ("auto_id", element_description.get("auto_id")),
                ("title", element_description.get("title")),
                ("control_type", element_description.get("control_type")),
                ("class_name", element_description.get("class_name"))
            ]
            
            for selector_type, selector_value in selectors:
                if not selector_value:
                    continue
                
                try:
                    kwargs = {selector_type: selector_value}
                    element = window.child_window(**kwargs)
                    
                    if element.exists():
                        rect = element.rectangle()
                        center = ((rect.left + rect.right) // 2, 
                                (rect.top + rect.bottom) // 2)
                        
                        self.logger.info(f"Element found via UIA: {selector_type}={selector_value}")
                        return VisionResult(True, center, 1.0, None, "uia")
                
                except Exception as e:
                    self.logger.debug(f"UIA selector failed: {selector_type}={selector_value}, {e}")
                    continue
            
            return VisionResult(False, None, 0.0, None, "uia_not_found")
        
        except Exception as e:
            self.logger.error(f"UIA detection error: {e}")
            return VisionResult(False, None, 0.0, None, "uia_error")
    
    def detect_element_ocr(self, target_text: str, language=None) -> VisionResult:
        """
        Detect element using OCR (Arabic + English)
        Fallback method when UIA fails
        
        Args:
            target_text: Text to search for
            language: OCR language (default from Config)
        
        Returns:
            VisionResult
        """
        if not OCR_AVAILABLE:
            return VisionResult(False, None, 0.0, None, "ocr_unavailable")
        
        if language is None:
            language = Config.OCR_LANGUAGES
        
        try:
            screenshot_path = self.capture_screen()
            if not screenshot_path:
                return VisionResult(False, None, 0.0, None, "ocr_screenshot_failed")
            
            # Configure Tesseract
            custom_config = f'--oem 3 --psm 6 -l {language}'
            
            # Extract text with bounding boxes
            image = Image.open(screenshot_path)
            ocr_data = pytesseract.image_to_data(image, config=custom_config, output_type=pytesseract.Output.DICT)
            
            # Search for target text
            for i, text in enumerate(ocr_data['text']):
                if target_text.lower() in text.lower():
                    x = ocr_data['left'][i] + ocr_data['width'][i] // 2
                    y = ocr_data['top'][i] + ocr_data['height'][i] // 2
                    confidence = ocr_data['conf'][i] / 100.0
                    
                    self.logger.info(f"Text '{target_text}' found via OCR at ({x}, {y})")
                    return VisionResult(True, (x, y), confidence, text, "ocr")
            
            return VisionResult(False, None, 0.0, None, "ocr_text_not_found")
        
        except Exception as e:
            self.logger.error(f"OCR detection error: {e}")
            return VisionResult(False, None, 0.0, None, "ocr_error")
    
    def detect_element_image(self, template_path: str, confidence=None) -> VisionResult:
        """
        Detect element using template matching (Computer Vision)
        Last resort fallback
        
        Args:
            template_path: Path to template image
            confidence: Confidence threshold (default from Config)
        
        Returns:
            VisionResult
        """
        if not PYAUTOGUI_AVAILABLE:
            return VisionResult(False, None, 0.0, None, "cv_unavailable")
        
        if confidence is None:
            confidence = Config.CV_CONFIDENCE_THRESHOLD
        
        try:
            location = pyautogui.locateCenterOnScreen(template_path, confidence=confidence)
            
            if location:
                self.logger.info(f"Element found via CV at {location}")
                return VisionResult(True, location, confidence, None, "computer_vision")
            else:
                return VisionResult(False, None, 0.0, None, "cv_not_found")
        
        except Exception as e:
            self.logger.error(f"Computer Vision detection error: {e}")
            return VisionResult(False, None, 0.0, None, "cv_error")
        


    def detect_element(self, window, element_description: Dict, fallback_strategy: str = "aggressive") -> VisionResult:
        """
        Detect element using multiple methods with fallback
        
        Args:
            window: PyWinAuto window object (can be None for OmniParser)
            element_description: Dict with element selectors
            fallback_strategy: "conservative" (UIA→OCR) or "aggressive" (UIA→OCR→OmniParser)
        
        Returns:
            VisionResult
        """
        FORCE_OMNIPARSER_TEST = True
        #OMNIPARSER TEST MODE
        if FORCE_OMNIPARSER_TEST:
            self.logger.warning("🧪 TEST MODE ACTIVE: Forcing all standard methods to fail")
            self.logger.warning("🧪 This will skip UIA, OCR, and CV - going straight to OmniParser")
                
            # Skip directly to OmniParser section
            search_text = element_description.get('text') or element_description.get('title') or element_description.get('auto_id')
                
            if search_text:
                self.logger.info(f"🔍 OmniParser searching for: '{search_text}'")
                result = self.detect_element_omniparser(search_text)
                    
                if result.element_found:
                    self.logger.info(f"✅ OMNIPARSER TEST SUCCESS! Found '{result.detected_text}' at {result.coordinates}")
                    return result
                else:
                    self.logger.error(f"❌ OmniParser failed in test mode: {result.method_used}")
                    return VisionResult(False, None, 0.0, None, "omniparser_test_failed")
            else:
                self.logger.error("❌ No search text provided for OmniParser test")
                return VisionResult(False, None, 0.0, None, "no_search_text")      





        # Try UIA first (if window provided)
        if window is not None:
            result = self.detect_element_uia(window, element_description)
            if result.element_found:
                self.logger.info(f"✓ Element found via UIA")
                return result
        
        # Try OCR fallback
        if 'text' in element_description:
            self.logger.info("UIA failed, trying OCR fallback...")
            result = self.detect_element_ocr(element_description['text'])
            if result.element_found:
                self.logger.info(f"✓ Element found via OCR")
                return result
        
        # Try computer vision (if template provided)
        if 'template' in element_description:
            self.logger.info("OCR failed, trying CV fallback...")
            result = self.detect_element_image(element_description['template'])
            if result.element_found:
                self.logger.info(f"✓ Element found via CV")
                return result
        
        # ========================================================================
        # CRITICAL: OmniParser Fallback (NEW CODE STARTS HERE)
        # ========================================================================
        if fallback_strategy == "aggressive":
            self.logger.warning("⚠️ All standard methods failed, activating OmniParser fallback...")
            
            # Try OmniParser as last resort
            search_text = element_description.get('text') or element_description.get('title') or element_description.get('auto_id')
            
            if search_text:
                self.logger.info(f"🔍 OmniParser searching for: '{search_text}'")
                result = self.detect_element_omniparser(search_text)
                
                if result.element_found:
                    self.logger.info(f"✅ OMNIPARSER FALLBACK SUCCESS! Found '{result.detected_text}' at {result.coordinates}")
                    return result
                else:
                    self.logger.warning(f"❌ OmniParser also failed: {result.method_used}")
            else:
                self.logger.warning("❌ No text/title to search with OmniParser")
        # ========================================================================
        # END OF NEW CODE
        # ========================================================================
        
        # All methods failed
        self.logger.error("❌ All detection methods exhausted (UIA → OCR → CV → OmniParser)")
        return VisionResult(False, None, 0.0, None, "all_methods_failed")