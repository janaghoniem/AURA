from .omniparser_detector import OmniParserDetector

__all__ = ['OmniParserDetector']
"""
Fallback detection methods for Vision Layer
"""

try:
    from .omniparser_detector import OmniParserDetector
    OMNIPARSER_AVAILABLE = True
except ImportError as e:
    OMNIPARSER_AVAILABLE = False
    OmniParserDetector = None
    print(f"⚠️ OmniParser not available: {e}")

__all__ = ['OmniParserDetector', 'OMNIPARSER_AVAILABLE']