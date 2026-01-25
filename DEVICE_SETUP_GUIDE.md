# Device Communication Setup Guide

## Overview
The backend can now detect and communicate with Android devices through HTTP endpoints. The Android Flutter app automatically registers itself and sends UI tree data to the backend.

## Architecture

### Device Registration Flow
```
Android App Start
    ↓
POST /device/android_device_1/register  ← App registers itself
    ↓
Device status: online
    ↓
Ready to receive commands
```

### Task Execution Flow
```
User: "open the Gmail app"
    ↓
Backend: Send to mobile_strategy
    ↓
Backend: GET /device/android_device_1/ui-tree  ← Get current screen
    ↓
LLM: Analyze and decide next action
    ↓
Backend: POST /device/android_device_1/action  ← Send action
    ↓
App: Execute action, update UI tree
    ↓
App: POST /device/android_device_1/ui-tree  ← Send updated tree
    ↓
Repeat until task complete
```

## Setup Instructions

### 1. Backend Setup

The backend already has device routes configured. Just make sure the server is running:

```bash
cd /Users/mohammedwalidadawy/Development/YUSR/backend
python server.py
```

The device endpoints will be available at `http://localhost:8000/device/*`

### 2. Android Emulator Setup

#### Start the emulator:
```bash
# List available emulators
emulator -list-avds

# Start a specific emulator (e.g., Pixel 6)
emulator -avd Pixel_6_API_34
```

#### Forward port (if needed):
```bash
adb forward tcp:8000 tcp:8000
```

### 3. Flutter App Setup

#### Install dependencies:
```bash
cd /Users/mohammedwalidadawy/Development/YUSR/android-app
flutter pub get
```

#### Run the app:
```bash
flutter run
```

The app will automatically:
1. Register with backend: `POST /device/android_device_1/register`
2. Send periodic status updates: `POST /device/android_device_1/status` (every 5 seconds)
3. Send UI tree on each action: `POST /device/android_device_1/ui-tree`

### 4. Verify Device Connection

#### Check if device is online:
```bash
curl http://localhost:8000/devices
```

Expected response:
```json
{
  "total_devices": 1,
  "devices": [
    {
      "device_id": "android_device_1",
      "name": "Flutter Device",
      "status": "online",
      "last_seen": null
    }
  ]
}
```

#### Check device status:
```bash
curl http://localhost:8000/device/android_device_1/status
```

#### Get current UI tree:
```bash
curl http://localhost:8000/device/android_device_1/ui-tree
```

### 5. Test Device Communication

Run the test script:
```bash
cd /Users/mohammedwalidadawy/Development/YUSR
python test_device_registration.py
```

This will test:
- Device registration
- Device status
- UI tree sending/retrieval
- Device listing

### 6. Send a Command to the Device

```bash
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{
    "message": "open the Gmail app",
    "device_type": "mobile",
    "session_id": "test_session_123"
  }'
```

The backend will:
1. Detect `device_type: mobile`
2. Route to mobile_strategy
3. Call the device registry to get device info
4. Get UI tree from device: `GET /device/android_device_1/ui-tree`
5. Use LLM to decide action
6. Send action to device: `POST /device/android_device_1/action`
7. Monitor for task completion

## Device Endpoints Reference

### Register Device
```
POST /device/{device_id}/register
Body: {
  "name": "Device Name",
  "android_version": "14",
  "device_model": "Pixel 6",
  "screen_width": 1080,
  "screen_height": 2340
}
Response: Device marked as "online"
```

### Send/Get UI Tree
```
GET /device/{device_id}/ui-tree
Returns current UI tree (set by last POST)

POST /device/{device_id}/ui-tree
Body: Semantic UI tree JSON
Updates the device's current screen state
```

### Send Action
```
POST /device/{device_id}/action
Body: {
  "action_type": "click|type|scroll|wait|global_action",
  "element_id": 1,
  "text": "search term",
  ...
}
```

### Device Status
```
GET /device/{device_id}/status
Returns device info and status

POST /device/{device_id}/status
Body: {
  "status": "online",
  "android_version": "14",
  ...
}
Updates device status
```

### List Devices
```
GET /devices
Returns: {
  "total_devices": 1,
  "devices": [
    {
      "device_id": "android_device_1",
      "name": "Flutter Device",
      "status": "online",
      "last_seen": null
    }
  ]
}
```

## Troubleshooting

### Device shows as "offline"
1. Check if Flutter app is running: `flutter run`
2. Check if app called registration endpoint
3. View backend logs for POST to `/device/*/register`

### Backend can't reach device
1. Verify port forwarding: `adb forward tcp:8000 tcp:8000`
2. Check emulator's network: Enable network in emulator settings
3. Verify backend URL in DeviceManager (should be `http://10.0.2.2:8000` for emulator)

### UI tree is empty
1. Make sure app sent POST to `/device/{device_id}/ui-tree`
2. Check backend logs for UI tree updates
3. Verify app is building proper UI tree JSON

### LLM can't see device
1. Ensure device status is "online"
2. Check coordinator is using correct device_id
3. View logs for device registry checks

## Files Modified

1. **[routes/device_routes.py](routes/device_routes.py)** - New device endpoint handlers
2. **[android-app/lib/main.dart](android-app/lib/main.dart)** - Added DeviceManager for registration
3. **[android-app/pubspec.yaml](android-app/pubspec.yaml)** - Added http package
4. **[agents/execution_agent/handlers/mobile_action_handler.py](agents/execution_agent/handlers/mobile_action_handler.py)** - Fixed ExecutionResult mapping
5. **[agents/coordinator_agent/coordinator_agent.py](agents/coordinator_agent/coordinator_agent.py)** - Updated device_id default to android_device_1
6. **[agents/utils/device_protocol.py](agents/utils/device_protocol.py)** - Migrated to ConfigDict
7. **[server.py](server.py)** - Added device_routes import

## Next Steps

1. ✅ Device registration working
2. ✅ UI tree communication established
3. ⏳ Action execution (backend → device)
4. ⏳ Full ReAct loop with LLM reasoning
5. ⏳ Gesture support (long press, swipe, etc.)
