# visual_test.py
"""
Visual test that shows you what OmniParser sees
"""

import sys
import logging
from pathlib import Path
import pyautogui
from PIL import Image, ImageDraw, ImageFont
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.execution_agent.layers.exec_agent_vision import VisionLayer

logging.basicConfig(level=logging.WARNING)  # Reduce noise
logger = logging.getLogger(__name__)

def visual_test():
    """Show visual detection results"""
    
    print("👁️ Visual OmniParser Test")
    print("="*60)
    print("This will show you what OmniParser detects on screen")
    print("="*60)
    
    # Initialize
    vision = VisionLayer(logger)
    
    # Take screenshot
    print("\n📸 Taking screenshot...")
    screenshot = pyautogui.screenshot()
    screenshot_path = "test_screenshot.png"
    screenshot.save(screenshot_path)
    print(f"✓ Screenshot saved: {screenshot_path}")
    
    # Try to get detection results
    print("\n🔍 Running detection...")
    
    if hasattr(vision, 'omniparser') and vision.omniparser:
        try:
            # Try to use OmniParser to detect all elements
            result = vision.omniparser.detect_all_elements(screenshot_path)
            
            if 'error' not in result:
                elements = result.get('elements', [])
                print(f"✓ Detected {len(elements)} elements")
                
                # Draw bounding boxes on screenshot
                img = Image.open(screenshot_path)
                draw = ImageDraw.Draw(img)
                
                # Try to load a font
                try:
                    font = ImageFont.truetype("arial.ttf", 12)
                except:
                    font = ImageFont.load_default()
                
                for i, elem in enumerate(elements[:20]):  # Show first 20
                    bbox = elem['bbox']
                    caption = elem.get('caption', 'Unknown')
                    conf = elem.get('confidence', 0)
                    
                    # Draw rectangle
                    draw.rectangle(bbox, outline="red", width=2)
                    
                    # Draw label
                    label = f"{i}: {caption[:20]} ({conf:.2f})"
                    draw.text((bbox[0], bbox[1] - 15), label, fill="red", font=font)
                
                # Save and show
                output_path = "detection_results.png"
                img.save(output_path)
                print(f"✓ Detection results saved: {output_path}")
                
                # Show the image
                plt.figure(figsize=(15, 10))
                plt.imshow(img)
                plt.title(f"OmniParser Detection - Found {len(elements)} elements")
                plt.axis('off')
                plt.show()
                
                # Print details of detected elements
                print("\n📋 Detected elements:")
                for i, elem in enumerate(elements[:10]):
                    print(f"\n{i+1}. {elem.get('caption', 'Unknown')}")
                    print(f"   Position: {elem.get('center', 'Unknown')}")
                    print(f"   Confidence: {elem.get('confidence', 0):.2f}")
                    print(f"   Bounding box: {elem.get('bbox', 'Unknown')}")
                
                if len(elements) > 10:
                    print(f"\n... and {len(elements) - 10} more elements")
                    
            else:
                print(f"❌ Detection error: {result.get('error')}")
                
        except Exception as e:
            print(f"❌ OmniParser error: {e}")
    else:
        print("❌ OmniParser not available")
    
    # Test simple element search
    print("\n" + "="*60)
    print("🔍 Testing element search...")
    
    test_queries = ["close", "search", "menu"]
    
    for query in test_queries:
        print(f"\nLooking for '{query}'...")
        try:
            result = vision.detect_element_omniparser(query)
            if result.element_found:
                print(f"  ✅ Found at {result.coordinates}")
                print(f"     Type: {result.text_detected}")
                print(f"     Confidence: {result.confidence:.2f}")
            else:
                print(f"  ❌ Not found")
        except Exception as e:
            print(f"  ⚠️ Error: {e}")

if __name__ == "__main__":
    visual_test()