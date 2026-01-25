# Device Registration & Communication Fix

## Problem
The backend couldn't recognize the Android device because:
1. Device started as "offline" in the registry
2. Android app wasn't registering with the backend
3. No UI tree endpoint communication established

## Solution

### 1. **Created Device Routes** ([routes/device_routes.py](routes/device_routes.py))
- `GET /device/{device_id}/ui-tree` - Get current screen UI tree
- `POST /device/{device_id}/ui-tree` - Receive UI tree updates from device
- `POST /device/{device_id}/action` - Send actions to device
- `POST /device/{device_id}/status` - Receive device status updates
- `GET/POST /device/{device_id}/register` - Register device with backend
- `GET /devices` - List all registered devices

Device status is automatically set to **"online"** when:
- Device calls `/device/{device_id}/register`
- Device sends UI tree via `/device/{device_id}/ui-tree`
- Device sends status via `/device/{device_id}/status`

### 2. **Updated Android App** ([android-app/lib/main.dart](android-app/lib/main.dart))
Added `DeviceManager` class that:
- Registers device on app startup: `POST /device/android_device_1/register`
- Sends UI tree before each action: `POST /device/android_device_1/ui-tree`
- Periodically sends status updates: `POST /device/android_device_1/status` (every 5 seconds)

Device IP for emulator: `10.0.2.2:8000` (Android emulator localhost gateway)

### 3. **Updated Backend Handler** ([agents/execution_agent/handlers/mobile_action_handler.py](agents/execution_agent/handlers/mobile_action_handler.py))
- Properly map `ExecutionResult.details` → `TaskResult.content`
- Handle None session_id gracefully
- Remove unused ExecutionResult fields

### 4. **Updated Coordinator** ([agents/coordinator_agent/coordinator_agent.py](agents/coordinator_agent/coordinator_agent.py))
- Changed default device_id from "default_device" → "android_device_1"
- Maps ExecutionResult correctly to TaskResult

### 5. **Updated Server** ([server.py](server.py))
- Import and register device_routes
- Add device routes to FastAPI app

### 6. **Updated Pydantic Models** ([agents/utils/device_protocol.py](agents/utils/device_protocol.py))
- Migrated from deprecated `class Config` to `ConfigDict`
- Made `session_id` optional in MobileTaskRequest

## Flow

```
1. Android App Starts
   ↓
2. App calls: POST /device/android_device_1/register
   ↓
3. Backend marks device as "online"
   ↓
4. User sends command to backend
   ↓
5. Coordinator routes to mobile_strategy
   ↓
6. Backend calls: GET /device/android_device_1/ui-tree
   ↓
7. Device returns current UI tree
   ↓
8. LLM decides action
   ↓
9. Backend sends action to Android app
   ↓
10. Repeat 6-9 until task complete
```

## Testing

### Start the Android emulator:
```bash
adb forward tcp:8000 tcp:8000
flutter run  # In android-app directory
```

### The device should now show as online:
```bash
curl http://localhost:8000/devices
```

Response:
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

### Send a mobile task:
```bash
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{
    "message": "open the Gmail app",
    "device_type": "mobile"
  }'
```

The backend should now be able to interact with the device!
