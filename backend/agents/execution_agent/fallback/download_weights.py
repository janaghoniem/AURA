# fixed_download.py
"""
Fixed OmniParser weights download
"""

import os
import requests
from pathlib import Path
import time

WEIGHTS_DIR = Path(__file__).parent / "weights"
ICON_CAPTION_DIR = WEIGHTS_DIR / "icon_caption_florence"
ICON_CAPTION_DIR.mkdir(parents=True, exist_ok=True)

# Files to download from the icon_caption_florence folder
FILES = [
    "config.json",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
    # "model.safetensors"  # Already downloaded
]

BASE_URL = "https://huggingface.co/microsoft/OmniParser-v2.0/raw/main/icon_caption_florence"

def download_file(filename):
    """Download a single file"""
    url = f"{BASE_URL}/{filename}"
    dest_path = ICON_CAPTION_DIR / filename
    
    if dest_path.exists():
        print(f"✓ Already exists: {filename}")
        return True
    
    print(f"Downloading {filename}...")
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        with open(dest_path, 'wb') as f:
            f.write(response.content)
        
        print(f"✓ Downloaded: {filename}")
        time.sleep(0.5)  # Be nice to the server
        return True
        
    except Exception as e:
        print(f"✗ Failed to download {filename}: {e}")
        return False

def main():
    print("="*70)
    print("Downloading missing OmniParser files")
    print("="*70)
    
    success_count = 0
    for filename in FILES:
        if download_file(filename):
            success_count += 1
    
    # Also download model.safetensors if missing
    model_path = ICON_CAPTION_DIR / "model.safetensors"
    if not model_path.exists():
        print("\nDownloading model.safetensors...")
        model_url = "https://huggingface.co/microsoft/OmniParser-v2.0/resolve/main/icon_caption_florence/model.safetensors"
        try:
            response = requests.get(model_url, stream=True, timeout=60)
            response.raise_for_status()
            
            with open(model_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print("✓ Downloaded model.safetensors")
            success_count += 1
        except Exception as e:
            print(f"✗ Failed to download model: {e}")
    
    print("\n" + "="*70)
    print(f"Downloaded {success_count}/{len(FILES)} files")
    
    # Check what we have
    print("\n📁 Files in icon_caption_florence folder:")
    for file in sorted(ICON_CAPTION_DIR.iterdir()):
        print(f"  {file.name} ({file.stat().st_size:,} bytes)")
    
    return success_count == len(FILES)

if __name__ == "__main__":
    main()