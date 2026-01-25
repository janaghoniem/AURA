"""
Device Routes
Endpoints for mobile device communication and UI automation

Handles:
- UI tree retrieval (GET /device/{device_id}/ui-tree)
- Action execution (POST /device/{device_id}/action)
- Device status (GET /device/{device_id}/status)
- Device list (GET /devices)

Android sends requests to these endpoints for:
- Sending current UI tree to backend
- Receiving actions to execute
- Reporting action results

Backend sends requests to:
- Get UI tree from Android device HTTP server
- Send actions to Android device
"""

from fastapi import APIRouter, HTTPException, Depends, Path, Body
from typing import Dict, Any, Optional, List
import logging
import httpx
import time

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/device", tags=["device"])

# In-memory device registry (replace with database in production)
DEVICE_REGISTRY: Dict[str, Dict[str, Any]] = {
    "default_device": {
        "device_id": "default_device",
        "name": "Default Device",
        "status": "offline",
        "last_seen": None,
        "screen_width": 1080,
        "screen_height": 2340,
        "android_version": "14",
        "app_name": "com.google.android.gm",
        "ui_tree": None
    }
}


# ============================================================================
# UI TREE ENDPOINTS
# ============================================================================

@router.get("/{device_id}/ui-tree")
async def get_ui_tree(device_id: str = Path(..., description="Device ID")):
    """
    Get current UI tree from device
    
    This endpoint is called by the backend to get the current screen state
    from the Android device. The Android device runs an HTTP server that
    exposes this endpoint.
    
    In production, this would proxy to the actual Android device:
    http://{device_ip}:8080/ui-tree
    """
    logger.info(f"📱 Getting UI tree from device: {device_id}")
    
    if device_id not in DEVICE_REGISTRY:
        logger.error(f"❌ Device not found: {device_id}")
        raise HTTPException(
            status_code=404,
            detail=f"Device {device_id} not found"
        )
    
    device = DEVICE_REGISTRY[device_id]
    
    if device["status"] == "offline":
        logger.warning(f"⚠️ Device is offline: {device_id}")
        raise HTTPException(
            status_code=503,
            detail=f"Device {device_id} is offline. Make sure the Android device is connected and the HTTP server is running."
        )
    
    # Return cached UI tree or empty tree
    if device.get("ui_tree"):
        return device["ui_tree"]
    
    # Default empty tree response
    return {
        "screen_id": f"screen_{device_id}",
        "device_id": device_id,
        "app_name": device.get("app_name", "unknown"),
        "app_package": "com.example.app",
        "screen_name": "Unknown Screen",
        "elements": [],
        "timestamp": 0,
        "screen_width": device.get("screen_width", 1080),
        "screen_height": device.get("screen_height", 2340)
    }


@router.post("/{device_id}/ui-tree")
async def update_ui_tree(
    device_id: str = Path(..., description="Device ID"),
    tree_data: Dict[str, Any] = None
):
    """
    Update UI tree from device
    
    This endpoint is called by the Android device to push the current UI tree
    to the backend. The Android HTTP server (running on device) calls this.
    
    Example Android call:
    POST http://{backend_ip}:8000/device/{device_id}/ui-tree
    {
        "screen_id": "screen_123",
        "device_id": "device_abc",
        "app_name": "Gmail",
        "elements": [...]
    }
    """
    logger.info(f"📥 Received UI tree update from device: {device_id}")
    
    if device_id not in DEVICE_REGISTRY:
        # Auto-register new devices
        DEVICE_REGISTRY[device_id] = {
            "device_id": device_id,
            "name": f"Device {device_id}",
            "status": "online",
            "last_seen": None,
            "screen_width": tree_data.get("screen_width", 1080) if tree_data else 1080,
            "screen_height": tree_data.get("screen_height", 2340) if tree_data else 2340,
            "ui_tree": tree_data
        }
        logger.info(f"✅ Auto-registered new device: {device_id}")
    else:
        device = DEVICE_REGISTRY[device_id]
        device["status"] = "online"
        device["ui_tree"] = tree_data
        if tree_data:
            device["screen_width"] = tree_data.get("screen_width", 1080)
            device["screen_height"] = tree_data.get("screen_height", 2340)
    
    return {
        "status": "ok",
        "message": f"UI tree updated for {device_id}"
    }


# ============================================================================
# ACTION ENDPOINTS
# ============================================================================

@router.post("/{device_id}/action")
async def execute_action(
    device_id: str = Path(..., description="Device ID"),
    action_data: Dict[str, Any] = Body(..., description="Action to execute")
):
    """
    Execute action on device
    
    Forwards the action to the Android device's HTTP server at port 9999.
    
    Example:
    POST http://{backend_ip}:8000/device/{device_id}/action
    {
        "action_type": "click",
        "element_id": 1,
        "action_id": "action_123"
    }
    """
    logger.info(f"⚡ Executing action on device: {device_id}")
    logger.info(f"   Action: {action_data}")
    
    if device_id not in DEVICE_REGISTRY:
        raise HTTPException(
            status_code=404,
            detail=f"Device {device_id} not found"
        )
    
    device = DEVICE_REGISTRY[device_id]
    
    if device["status"] == "offline":
        logger.warning(f"⚠️ Device {device_id} is offline, cannot execute action")
        return {
            "action_id": action_data.get("action_id") if action_data else "unknown",
            "success": False,
            "error": "Device is offline",
            "execution_time_ms": 0
        }
    
    # Forward to Android device HTTP server (localhost:9999 for emulator)
    # In production, would be the device's actual IP
    try:
        import httpx
        
        # For emulator: Android device runs on localhost:9999
        # For physical device: would need IP configuration
        android_url = "http://localhost:9999/action"
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                android_url,
                json=action_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ Action executed successfully on device")
                return result
            else:
                logger.error(f"❌ Device returned error: {response.status_code}")
                return {
                    "action_id": action_data.get("action_id") if action_data else "unknown",
                    "success": False,
                    "error": f"Device error: {response.status_code}",
                    "execution_time_ms": 0
                }
    except Exception as e:
        logger.warning(f"⚠️ Could not forward to Android device: {e}")
        logger.info(f"   Device may be running on different host/port")
        
        # Return success=false to indicate action wasn't executed
        return {
            "action_id": action_data.get("action_id") if action_data else "unknown",
            "success": False,
            "error": f"Cannot reach device: {str(e)}",
            "execution_time_ms": 0
        }


@router.post("/{device_id}/execute")
async def execute_action_alias(
    device_id: str = Path(..., description="Device ID"),
    action_data: Dict[str, Any] = Body(..., description="Action to execute")
):
    """Alias for /action endpoint (for backward compatibility)"""
    return await execute_action(device_id, action_data)


# ============================================================================
# DEVICE STATUS ENDPOINTS
# ============================================================================

@router.get("/{device_id}/status")
async def get_device_status(device_id: str = Path(..., description="Device ID")):
    """Get device status and metadata"""
    logger.info(f"📊 Getting status for device: {device_id}")
    
    if device_id not in DEVICE_REGISTRY:
        raise HTTPException(
            status_code=404,
            detail=f"Device {device_id} not found"
        )
    
    device = DEVICE_REGISTRY[device_id]
    
    return {
        "device_id": device["device_id"],
        "name": device["name"],
        "status": device["status"],
        "last_seen": device["last_seen"],
        "screen_width": device.get("screen_width"),
        "screen_height": device.get("screen_height"),
        "android_version": device.get("android_version"),
        "app_name": device.get("app_name")
    }


@router.post("/{device_id}/status")
async def update_device_status(
    device_id: str = Path(..., description="Device ID"),
    status_data: Dict[str, Any] = None
):
    """
    Update device status
    
    Called by Android device to report its status
    
    Example:
    POST http://{backend_ip}:8000/device/{device_id}/status
    {
        "status": "online",
        "android_version": "14",
        "app_name": "com.google.android.gm",
        "screen_width": 1080,
        "screen_height": 2340
    }
    """
    logger.info(f"📝 Updating status for device: {device_id}")
    
    if device_id not in DEVICE_REGISTRY:
        DEVICE_REGISTRY[device_id] = {
            "device_id": device_id,
            "name": f"Device {device_id}",
            "status": "online",
            "last_seen": None,
            "screen_width": 1080,
            "screen_height": 2340
        }
    
    device = DEVICE_REGISTRY[device_id]
    device["status"] = "online"  # Always mark as online when status is sent
    
    if status_data:
        device["android_version"] = status_data.get("android_version")
        device["app_name"] = status_data.get("app_name")
        device["screen_width"] = status_data.get("screen_width", 1080)
        device["screen_height"] = status_data.get("screen_height", 2340)
    
    return {
        "status": "ok",
        "message": f"Status updated for {device_id}"
    }


# ============================================================================
# DEVICE LIST ENDPOINT
# ============================================================================

@router.get("")
async def list_devices():
    """List all registered devices"""
    logger.info(f"📋 Listing {len(DEVICE_REGISTRY)} registered devices")
    
    return {
        "total_devices": len(DEVICE_REGISTRY),
        "devices": [
            {
                "device_id": device["device_id"],
                "name": device["name"],
                "status": device["status"],
                "last_seen": device["last_seen"]
            }
            for device in DEVICE_REGISTRY.values()
        ]
    }


@router.get("/{device_id}/register")
async def register_device_get(
    device_id: str = Path(..., description="Device ID"),
    name: Optional[str] = None,
    android_version: Optional[str] = None
):
    """
    Register device (GET endpoint for easy testing)
    
    Used during Android app startup to register with backend
    
    Example:
    GET http://{backend_ip}:8000/device/{device_id}/register?name=MyPhone&android_version=14
    """
    logger.info(f"✅ Registering device: {device_id}")
    
    if device_id not in DEVICE_REGISTRY:
        DEVICE_REGISTRY[device_id] = {
            "device_id": device_id,
            "name": name or f"Device {device_id}",
            "status": "online",
            "last_seen": None,
            "android_version": android_version,
            "screen_width": 1080,
            "screen_height": 2340
        }
        logger.info(f"✅ Device registered: {device_id}")
    else:
        device = DEVICE_REGISTRY[device_id]
        device["status"] = "online"
        if name:
            device["name"] = name
        if android_version:
            device["android_version"] = android_version
    
    return {
        "status": "ok",
        "message": f"Device {device_id} registered",
        "device_info": DEVICE_REGISTRY[device_id]
    }


@router.post("/{device_id}/register")
async def register_device_post(
    device_id: str = Path(..., description="Device ID"),
    device_data: Dict[str, Any] = None
):
    """
    Register device (POST endpoint for detailed info)
    
    Example:
    POST http://{backend_ip}:8000/device/{device_id}/register
    {
        "name": "My Device",
        "android_version": "14",
        "device_model": "Pixel 6",
        "screen_width": 1080,
        "screen_height": 2340
    }
    """
    logger.info(f"✅ Registering device via POST: {device_id}")
    
    if device_id not in DEVICE_REGISTRY:
        DEVICE_REGISTRY[device_id] = {
            "device_id": device_id,
            "name": device_data.get("name", f"Device {device_id}") if device_data else f"Device {device_id}",
            "status": "online",
            "last_seen": None,
            "screen_width": 1080,
            "screen_height": 2340
        }
    
    device = DEVICE_REGISTRY[device_id]
    device["status"] = "online"  # Mark as online when registering
    
    if device_data:
        device["name"] = device_data.get("name", device["name"])
        device["android_version"] = device_data.get("android_version")
        device["device_model"] = device_data.get("device_model")
        device["screen_width"] = device_data.get("screen_width", 1080)
        device["screen_height"] = device_data.get("screen_height", 2340)
    
    logger.info(f"✅ Device {device_id} is now ONLINE")
    
    return {
        "status": "ok",
        "message": f"Device {device_id} registered and online",
        "device_info": device
    }

# ============================================================================
# REACT LOOP ENDPOINTS (for LLM-driven automation)
# ============================================================================

# Store pending actions and results per device
PENDING_ACTIONS: Dict[str, List[Dict[str, Any]]] = {}
ACTION_RESULTS: Dict[str, List[Dict[str, Any]]] = {}


@router.get("/{device_id}/pending-actions")
async def get_pending_actions(device_id: str = Path(..., description="Device ID")):
    """
    Get pending actions for a device
    
    Called by ActionPollingService on Android device to retrieve actions
    from the backend that need to be executed.
    
    Returns list of actions to execute.
    """
    logger.info(f"📥 Android polling for actions: {device_id}")
    
    if device_id not in PENDING_ACTIONS:
        PENDING_ACTIONS[device_id] = []
    
    actions = PENDING_ACTIONS[device_id]
    
    if actions:
        logger.info(f"   📤 Returning {len(actions)} pending actions")
    
    # Return all pending actions
    response = {
        "actions": actions,
        "count": len(actions)
    }
    
    # Clear pending actions after returning them
    PENDING_ACTIONS[device_id] = []
    
    return response


@router.post("/{device_id}/action-result")
async def receive_action_result(
    device_id: str = Path(..., description="Device ID"),
    result_data: Dict[str, Any] = None
):
    """
    Receive action execution result from Android device
    
    Called by ActionPollingService on Android after executing an action,
    to report back the result to the backend.
    
    Example:
    POST http://{backend_ip}:8000/device/{device_id}/action-result
    {
        "action_id": "action_123",
        "success": true,
        "execution_time_ms": 150,
        "error": null
    }
    """
    logger.info(f"✅ Received action result from device: {device_id}")
    
    if result_data:
        logger.info(f"   Action ID: {result_data.get('action_id')}")
        logger.info(f"   Success: {result_data.get('success')}")
        if not result_data.get('success'):
            logger.warning(f"   Error: {result_data.get('error')}")
    
    if device_id not in ACTION_RESULTS:
        ACTION_RESULTS[device_id] = []
    
    # Store the result
    ACTION_RESULTS[device_id].append(result_data)
    
    return {
        "status": "ok",
        "message": "Action result received"
    }


@router.post("/{device_id}/execute-action")
async def execute_action_on_device(
    device_id: str = Path(..., description="Device ID"),
    action_data: Dict[str, Any] = Body(..., description="Action to execute")
):
    """
    Execute an action on the device
    
    Called by MobileReActStrategy to send an action to the Android device.
    This queues the action for the ActionPollingService to pick up.
    
    Example:
    POST http://{backend_ip}:8000/device/{device_id}/execute-action
    {
        "action_id": "action_123",
        "action_type": "click",
        "element_id": 5
    }
    """
    logger.info(f"⚡ Queueing action for device: {device_id}")
    logger.info(f"   Action: {action_data.get('action_type')}")
    
    if device_id not in DEVICE_REGISTRY:
        raise HTTPException(
            status_code=404,
            detail=f"Device {device_id} not found"
        )
    
    device = DEVICE_REGISTRY[device_id]
    
    if device["status"] == "offline":
        logger.warning(f"⚠️ Device {device_id} is offline")
        return {
            "action_id": action_data.get("action_id", "unknown"),
            "success": False,
            "error": "Device is offline",
            "execution_time_ms": 0
        }
    
    # Convert navigate_home to goToHome for the action server
    if action_data.get("action_type") == "navigate_home":
        logger.info(f"🏠 navigate_home request - queueing as goToHome for device: {device_id}")
        action_data["action_type"] = "goToHome"
    
    # Queue the action for polling
    if device_id not in PENDING_ACTIONS:
        PENDING_ACTIONS[device_id] = []
    
    PENDING_ACTIONS[device_id].append(action_data)
    logger.info(f"✅ Action queued for polling: {action_data.get('action_type')}")
    
    # Return immediate success - actual execution happens on Android
    return {
        "action_id": action_data.get("action_id", "unknown"),
        "success": True,
        "error": None,
        "execution_time_ms": 0
    }