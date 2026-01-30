"""
Test OmniParser integration
Run from backend directory: python -m agents.execution_agent.test_omniparser
"""

import sys
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Now imports should work
from agents.execution_agent.layers.exec_agent_vision import VisionLayer

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_omniparser():
    """Test OmniParser detection on current screen"""
    
    logger.info("="*70)
    logger.info("OMNIPARSER TEST - Make sure you have some UI visible!")
    logger.info("="*70)
    
    # Initialize vision layer
    try:
        vision = VisionLayer(logger)
        logger.info("✓ VisionLayer initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize VisionLayer: {e}")
        return
    
    # Check if OmniParser is available
    if not hasattr(vision, 'omniparser') or vision.omniparser_detector is None:
        logger.error("❌ OmniParser not available")
        logger.info("Make sure you:")
        logger.info("  1. Created fallback/__init__.py")
        logger.info("  2. Ran: python fallback/download_weights.py")
        logger.info("  3. Installed: pip install -r fallback/requirements.txt")
        return
    
    logger.info("✓ OmniParser available")
    
    # Test 1: Detect all elements on screen
    logger.info("\n" + "="*70)
    logger.info("TEST 1: Detect all UI elements on current screen")
    logger.info("="*70)
    
    try:
        result = vision.omniparser_detector.detect_all_elements()
        
        if 'error' in result:
            logger.error(f"❌ Detection failed: {result['error']}")
        else:
            total = result.get('total_elements', 0)
            logger.info(f"✅ Found {total} elements on screen")
            
            # Show first 10 elements
            for i, elem in enumerate(result.get('elements', [])[:10], 1):
                logger.info(f"\n  Element {i}:")
                logger.info(f"    Caption: {elem['caption']}")
                logger.info(f"    Position: {elem['center']}")
                logger.info(f"    Confidence: {elem['confidence']:.2f}")
    
    except Exception as e:
        logger.error(f"❌ Test 1 failed: {e}", exc_info=True)
    
    # Test 2: Search for specific elements
    logger.info("\n" + "="*70)
    logger.info("TEST 2: Search for specific UI elements")
    logger.info("="*70)
    
    # Common UI elements to search for
    test_queries = [
        "close button",
        "minimize button", 
        "maximize button",
        "search",
        "menu",
        "start button",
        "taskbar"
    ]
    
    found_count = 0
    for query in test_queries:
        try:
            logger.info(f"\n🔍 Searching for: '{query}'")
            result = vision.detect_element_omniparser(query)
            
            if result.element_found:
                logger.info(f"  ✅ FOUND: {result.detected_text}")
                logger.info(f"     Position: {result.coordinates}")
                logger.info(f"     Confidence: {result.confidence:.2f}")
                found_count += 1
            else:
                logger.info(f"  ❌ Not found ({result.method_used})")
        
        except Exception as e:
            logger.error(f"  ❌ Search failed: {e}")
    
    logger.info(f"\n{'='*70}")
    logger.info(f"Found {found_count}/{len(test_queries)} elements")
    
    # Test 3: Unified detection with fallback chain
    logger.info("\n" + "="*70)
    logger.info("TEST 3: Unified detection with fallback chain")
    logger.info("="*70)
    
    try:
        # This will try: OCR -> OmniParser (since we don't have UIA window)
        element_desc = {
            "text": "close button"
        }
        
        logger.info("Testing fallback chain for 'close button'...")
        result = vision.detect_element(element_desc, fallback_strategy="aggressive")
        
        logger.info(f"\nResult:")
        logger.info(f"  Method used: {result.method_used}")
        logger.info(f"  Success: {result.element_found}")
        if result.element_found:
            logger.info(f"  Position: {result.coordinates}")
            logger.info(f"  Confidence: {result.confidence:.2f}")
    
    except Exception as e:
        logger.error(f"❌ Test 3 failed: {e}", exc_info=True)
    
    logger.info("\n" + "="*70)
    logger.info("TESTS COMPLETE")
    logger.info("="*70)

if __name__ == "__main__":
    test_omniparser()