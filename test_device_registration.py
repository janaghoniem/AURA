#!/usr/bin/env python3
"""
Test script to verify device registration and communication
"""

import requests
import json
import time
import sys

BACKEND_URL = "http://localhost:8000"

def test_device_endpoints():
    """Test device registration and communication"""
    
    print("\n" + "="*60)
    print("DEVICE REGISTRATION TEST")
    print("="*60)
    
    # 1. Check initial device status
    print("\n1️⃣ Checking initial device registry...")
    try:
        resp = requests.get(f"{BACKEND_URL}/devices")
        devices = resp.json()
        print(f"   ✅ Found {devices.get('total_devices', 0)} devices")
        for device in devices.get('devices', []):
            print(f"      - {device['device_id']}: {device['status']}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    # 2. Register a test device
    print("\n2️⃣ Registering test device...")
    try:
        resp = requests.post(
            f"{BACKEND_URL}/device/test_device_1/register",
            json={
                "name": "Test Device",
                "android_version": "14",
                "device_model": "Pixel 6",
                "screen_width": 1080,
                "screen_height": 2340
            }
        )
        if resp.status_code == 200:
            print(f"   ✅ Device registered successfully")
            print(f"   Status: {resp.json()['message']}")
        else:
            print(f"   ❌ Registration failed: {resp.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    # 3. Check device is online
    print("\n3️⃣ Checking device status...")
    try:
        resp = requests.get(f"{BACKEND_URL}/device/test_device_1/status")
        if resp.status_code == 200:
            device_info = resp.json()
            print(f"   ✅ Device status: {device_info['status']}")
            print(f"   Name: {device_info['name']}")
        else:
            print(f"   ❌ Status check failed: {resp.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    # 4. Send a UI tree
    print("\n4️⃣ Sending UI tree to backend...")
    try:
        ui_tree = {
            "screen_id": "screen_test",
            "device_id": "test_device_1",
            "app_name": "TestApp",
            "app_package": "com.test.app",
            "screen_name": "Main",
            "elements": [
                {
                    "element_id": 1,
                    "type": "button",
                    "text": "Test Button",
                    "clickable": True,
                    "focusable": True
                }
            ],
            "timestamp": time.time(),
            "screen_width": 1080,
            "screen_height": 2340
        }
        
        resp = requests.post(
            f"{BACKEND_URL}/device/test_device_1/ui-tree",
            json=ui_tree
        )
        if resp.status_code == 200:
            print(f"   ✅ UI tree sent successfully")
        else:
            print(f"   ❌ UI tree send failed: {resp.status_code}")
            print(f"   Response: {resp.text}")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    # 5. Retrieve UI tree
    print("\n5️⃣ Retrieving UI tree from backend...")
    try:
        resp = requests.get(f"{BACKEND_URL}/device/test_device_1/ui-tree")
        if resp.status_code == 200:
            tree = resp.json()
            print(f"   ✅ UI tree retrieved")
            print(f"   App: {tree.get('app_name')}")
            print(f"   Elements: {len(tree.get('elements', []))}")
        else:
            print(f"   ❌ UI tree retrieval failed: {resp.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    # 6. List all devices
    print("\n6️⃣ Listing all devices...")
    try:
        resp = requests.get(f"{BACKEND_URL}/devices")
        devices = resp.json()
        print(f"   ✅ Found {devices.get('total_devices', 0)} devices:")
        for device in devices.get('devices', []):
            status_emoji = "🟢" if device['status'] == 'online' else "🔴"
            print(f"      {status_emoji} {device['device_id']}: {device['status']}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    print("\n" + "="*60)
    print("✅ ALL TESTS PASSED!")
    print("="*60 + "\n")
    return True

if __name__ == "__main__":
    try:
        success = test_device_endpoints()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n❌ Test interrupted by user")
        sys.exit(1)
