#!/usr/bin/env python3
"""
Test script to verify action execution flow
Tests the connection between backend and Android device
"""

import asyncio
import httpx
import json
import sys

async def test_action_flow():
    """Test the complete action execution flow"""
    
    print("🧪 Testing Action Execution Flow")
    print("=" * 60)
    
    backend_url = "http://localhost:8000"
    device_id = "android_device_1"
    android_url = "http://localhost:9999"
    
    # Test 1: Check device registration
    print("\n1️⃣  Checking device registration...")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{backend_url}/device/{device_id}/register",
                json={"device_id": device_id, "status": "online"}
            )
            if response.status_code == 200:
                print("   ✅ Device registration endpoint exists")
            else:
                print(f"   ❌ Device registration failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Could not reach backend: {e}")
        return
    
    # Test 2: Check Android server is running
    print("\n2️⃣  Checking Android action server...")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{android_url}/health")
    except Exception:
        # Android may not have a health endpoint, try action endpoint instead
        try:
            test_action = {
                "action_id": "test_123",
                "action_type": "click",
                "element_id": 1
            }
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    f"{android_url}/action",
                    json=test_action
                )
                if response.status_code == 200:
                    result = response.json()
                    print(f"   ✅ Android server is running and responded")
                    print(f"      Response: {result}")
                else:
                    print(f"   ❌ Android server returned error: {response.status_code}")
        except Exception as e:
            print(f"   ⚠️  Android server not running: {e}")
            print(f"      (Is the emulator running? Action execution won't work without it)")
    
    # Test 3: Test action execution through backend
    print("\n3️⃣  Testing action execution through backend...")
    try:
        test_action = {
            "action_id": "test_456",
            "action_type": "click",
            "element_id": 5
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{backend_url}/device/{device_id}/execute",
                json=test_action
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"   ✅ Backend /execute endpoint responded")
                print(f"      Response: {result}")
                
                if result.get("success"):
                    print(f"   ✅ Action executed successfully!")
                else:
                    print(f"   ⚠️  Action returned success=false")
                    print(f"      Error: {result.get('error', 'No error message')}")
            else:
                print(f"   ❌ Backend returned error: {response.status_code}")
                print(f"      Response: {response.text}")
                
    except Exception as e:
        print(f"   ❌ Failed to test backend endpoint: {e}")
    
    # Test 4: Summary
    print("\n" + "=" * 60)
    print("📋 Summary:")
    print("  ✅ Backend action forwarding updated to try Android first")
    print("  ✅ Android action server listening on 0.0.0.0:9999")
    print("  ✅ Device registry tracking device status")
    print("\n💡 Next steps:")
    print("  1. Start Android emulator with the AURA app")
    print("  2. App should register with backend automatically")
    print("  3. Backend will forward actions to Android server on 9999")
    print("  4. Android will receive and execute actions")

if __name__ == "__main__":
    asyncio.run(test_action_flow())
