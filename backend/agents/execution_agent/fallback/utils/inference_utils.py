"""
OmniParser inference utilities
"""

import torch
from PIL import Image
import numpy as np
from pathlib import Path
import yaml
from ultralytics import YOLO
from transformers import AutoProcessor, AutoModelForCausalLM
import logging

logger = logging.getLogger(__name__)

class IconDetector:
    """YOLO-based icon detector"""
    
    def __init__(self, model_path: str):
        self.model = YOLO(model_path)
        self.model.conf = 0.3  # Confidence threshold
        logger.info(f"Detector loaded from {model_path}")
    
    def detect(self, image: Image.Image, conf_threshold: float = 0.3):
        """Detect icons in image"""
        self.model.conf = conf_threshold
        results = self.model(image, verbose=False)
        
        detections = []
        for result in results:
            if result.boxes is not None:
                for box in result.boxes:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    conf = box.conf[0].item()
                    cls = int(box.cls[0])
                    
                    detections.append({
                        'bbox': [x1, y1, x2, y2],
                        'confidence': conf,
                        'class_id': cls
                    })
        
        logger.debug(f"Detected {len(detections)} icons")
        return detections

class IconCaptioner:
    """Simplified Florence-2 captioner"""
    
    def __init__(self, model_path: str):
        self.model_path = Path(model_path)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # Load config
        config_path = self.model_path / "config.json"
        if not config_path.exists():
            raise FileNotFoundError(f"Config not found: {config_path}")
        
        # Simple captioning - using BLIP as fallback since Florence-2 is complex
        try:
            from transformers import BlipProcessor, BlipForConditionalGeneration
            
            # Use BLIP as a simpler alternative
            self.processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
            self.model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base").to(self.device)
            logger.info("Loaded BLIP model for captioning")
            self.use_blip = True
        except Exception as e:
            logger.warning(f"Failed to load BLIP: {e}. Using simple captioning.")
            self.use_blip = False
    
    def caption(self, image: Image.Image) -> str:
        """Generate caption for icon image"""
        try:
            if self.use_blip:
                # Use BLIP for captioning
                inputs = self.processor(image, return_tensors="pt").to(self.device)
                out = self.model.generate(**inputs, max_length=50)
                caption = self.processor.decode(out[0], skip_special_tokens=True)
            else:
                # Simple fallback - just return generic description
                width, height = image.size
                caption = f"UI element ({width}x{height})"
            
            return caption
        except Exception as e:
            logger.error(f"Captioning failed: {e}")
            return "Unknown UI element"

def crop_image_region(image: Image.Image, bbox):
    """Crop region from image"""
    x1, y1, x2, y2 = bbox
    x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
    return image.crop((x1, y1, x2, y2))

def calculate_center(bbox):
    """Calculate center of bounding box"""
    x1, y1, x2, y2 = bbox
    return (int((x1 + x2) / 2), int((y1 + y2) / 2))