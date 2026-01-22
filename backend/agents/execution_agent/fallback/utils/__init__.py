"""
OmniParser utilities
"""

try:
    from .inference_utils import IconDetector, IconCaptioner, crop_image_region, calculate_center
    __all__ = ['IconDetector', 'IconCaptioner', 'crop_image_region', 'calculate_center']
except ImportError as e:
    print(f"⚠️ OmniParser utils not available: {e}")
    __all__ = []