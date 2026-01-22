"""
OmniParser UI Element Detector
Integrates with existing VisionLayer as advanced fallback
"""

import logging
from pathlib import Path
from typing import Optional, Dict
from PIL import Image
import pyautogui

# Import from parent layers
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.exec_agent_models import VisionResult

# Import OmniParser utilities
from .utils import IconDetector, IconCaptioner, crop_image_region, calculate_center


class OmniParserDetector:
    """
    OmniParser-based UI element detection
    Advanced fallback when UIA/OCR/CV fail
    """
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.initialized = False
        self.detector = None
        self.captioner = None
        
        # Paths
        self.weights_dir = Path(__file__).parent / "weights"
        self.detector_path = self.weights_dir / "icon_detect" / "model.pt"
        self.captioner_path = self.weights_dir / "icon_caption_florence"
        
        # Lazy initialization (only load models when first used)
        self._check_models_exist()
    
    def _check_models_exist(self):
        """Check if model weights are downloaded"""
        if not self.detector_path.exists():
            self.logger.warning(f"⚠️ OmniParser detector model not found at {self.detector_path}")
            self.logger.warning("Run: python fallback/download_weights.py")
            return False
        
        if not self.captioner_path.exists():
            self.logger.warning(f"⚠️ OmniParser captioner model not found at {self.captioner_path}")
            return False
        
        return True
    
    def _initialize_models(self):
        """Lazy load models (only when first detection is needed)"""
        if self.initialized:
            return True
        
        if not self._check_models_exist():
            self.logger.error("❌ OmniParser models not available")
            return False
        
        try:
            self.logger.info("🔄 Loading OmniParser models...")
            
            # Load detector
            self.detector = IconDetector(str(self.detector_path))
            self.logger.info("✓ Detector loaded")
            
            # Load captioner
            self.captioner = IconCaptioner(str(self.captioner_path))
            self.logger.info("✓ Captioner loaded")
            
            self.initialized = True
            self.logger.info("✅ OmniParser initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize OmniParser: {e}")
            self.initialized = False
            return False
    
    def detect_element_by_text(self, target_text: str, screenshot_path: Optional[str] = None) -> VisionResult:
        """
        Detect UI element by text description
        
        Args:
            target_text: Text describing the element (e.g., "submit button", "search icon")
            screenshot_path: Optional path to screenshot (will capture new one if None)
        
        Returns:
            VisionResult matching your existing format
        """
        # Initialize models if needed
        if not self._initialize_models():
            return VisionResult(False, None, 0.0, None, "omniparser_unavailable")
        
        try:
            # Capture screenshot if not provided
            if screenshot_path is None:
                screenshot = pyautogui.screenshot()
                image = screenshot
            else:
                image = Image.open(screenshot_path)
            
            # Step 1: Detect all UI elements
            self.logger.info(f"🔍 Detecting UI elements...")
            detections = self.detector.detect(image, conf_threshold=0.3)
            
            if not detections:
                self.logger.info("No elements detected")
                return VisionResult(False, None, 0.0, None, "omniparser_no_elements")
            
            self.logger.info(f"Found {len(detections)} elements")
            
            # Step 2: Caption each detection and find best match
            best_match = None
            best_score = 0.0
            target_lower = target_text.lower()
            
            for detection in detections:
                # Crop element region
                bbox = detection['bbox']
                element_img = crop_image_region(image, bbox)
                
                # Generate caption
                caption = self.captioner.caption(element_img)
                caption_lower = caption.lower()
                
                # Simple text matching (you can improve this with embeddings/semantic search)
                if target_lower in caption_lower or caption_lower in target_lower:
                    score = detection['confidence']
                    
                    if score > best_score:
                        best_score = score
                        best_match = {
                            'bbox': bbox,
                            'caption': caption,
                            'confidence': score
                        }
                    
                    self.logger.debug(f"Match found: '{caption}' (conf: {score:.2f})")
            
            # Return result
            if best_match:
                center = calculate_center(best_match['bbox'])
                self.logger.info(f"✅ Element found: '{best_match['caption']}' at {center}")
                
                return VisionResult(
                    success=True,
                    coordinates=center,
                    confidence=best_match['confidence'],
                    detected_text=best_match['caption'],
                    method="omniparser"
                )
            else:
                self.logger.info(f"❌ No match found for '{target_text}'")
                return VisionResult(False, None, 0.0, None, "omniparser_no_match")
        
        except Exception as e:
            self.logger.error(f"❌ OmniParser detection failed: {e}")
            return VisionResult(False, None, 0.0, None, f"omniparser_error: {e}")
    
    def detect_all_elements(self, screenshot_path: Optional[str] = None) -> Dict:
        """
        Detect and caption all UI elements (useful for debugging)
        
        Returns:
            Dict with all detected elements and their captions
        """
        if not self._initialize_models():
            return {"error": "OmniParser unavailable"}
        
        try:
            # Get image
            if screenshot_path is None:
                image = pyautogui.screenshot()
            else:
                image = Image.open(screenshot_path)
            
            # Detect
            detections = self.detector.detect(image)
            
            # Caption each
            results = []
            for i, det in enumerate(detections):
                bbox = det['bbox']
                element_img = crop_image_region(image, bbox)
                caption = self.captioner.caption(element_img)
                center = calculate_center(bbox)
                
                results.append({
                    'id': i,
                    'bbox': bbox,
                    'center': center,
                    'caption': caption,
                    'confidence': det['confidence']
                })
            
            return {
                'total_elements': len(results),
                'elements': results
            }
        
        except Exception as e:
            return {"error": str(e)}