# 🎯 Action Execution Flow - AURA Mobile Automation

## Overview
Complete flow from backend task execution to Android device action execution.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ BACKEND SERVER (Port 8000)                                       │
│                                                                   │
│  Coordinator Agent                                               │
│  └─> Mobile Task Request                                         │
│      └─> Execution Agent (Mobile Strategy)                      │
│          │                                                        │
│          ├─> 1. GET /device/{id}/ui-tree  ────────────────┐   │
│          │                                                  │    │
│          ├─> 2. Parse UI to LLM                            │    │
│          │      Groq: "What action next?"                  │    │
│          │                                                  │    │
│          ├─> 3. LLM Response: JSON Action                  │    │
│          │      {action_type, element_id, ...}             │    │
│          │                                                  │    │
│          ├─> 4. POST /device/{id}/execute  ──────────────┬┴──┐ │
│          │       (tries android:9999 first)  │          │    │
│          │                                    │          ▼    │
│          └─────── 5. ActionResult ◄──────────┴──────────┘    │
│                   {success, error, time}                       │
│                                                                 │
└────────────────────────────────┬──────────────────────────────┘
                                 │
                    HTTP POST /action
                    (action_id, action_type, ...)
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ ANDROID DEVICE (Port 9999)                                       │
│                                                                   │
│  HttpServer (localhost:9999)                                     │
│  └─> Request: POST /action                                      │
│      │                                                            │
│      ├─> Parse JSON action                                      │
│      │                                                            │
│      ├─> DeviceManager.executeAction()                          │
│      │   └─> action_type switch:                                │
│      │       ├─> "click"   → UI click (coordinates)            │
│      │       ├─> "type"    → Keyboard input                     │
│      │       ├─> "scroll"  → Scroll view                        │
│      │       ├─> "wait"    → Delay                              │
│      │       └─> "global"  → Back/Home/Recent                   │
│      │                                                            │
│      ├─> Return ActionResult                                    │
│      │   {action_id, success, error?, execution_time_ms}        │
│      │                                                            │
│      └─> Backend receives response                              │
│          (closes perception loop in ReAct)                       │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Step-by-Step Flow

### Phase 1: Device Registration & Initialization
```
1. Android App Starts
   └─> registerWithBackend()
       └─> POST /device/android_device_1/register
           Backend: Creates device in DEVICE_REGISTRY with status="online"

2. Android Starts Action Server
   └─> _startActionServer()
       └─> HttpServer.bind("0.0.0.0", 9999)
           Listens for POST requests to /action
```

### Phase 2: Task Execution Loop (ReAct)
```
3. Backend Mobile Strategy (5-step loop):
   
   Step 1: OBSERVE - Get UI Tree
   ├─> GET /device/{device_id}/ui-tree
   ├─> Backend caches current UI
   └─> Returns SemanticUITree
   
   Step 2: ACT - Generate Action
   ├─> Send UI tree to Groq LLM
   ├─> LLM prompt: "Given this UI, what's the next action to [task]?"
   └─> LLM returns JSON: {"action_type": "click", "element_id": 3}
   
   Step 3: EXECUTE - Send to Device
   ├─> Build UIAction object with action_id, action_type, params
   ├─> Try: POST http://localhost:9999/action (direct to device)
   ├─> Fallback: POST /device/{device_id}/execute (backend forwarding)
   └─> Wait for ActionResult response
   
   Step 4: REFLECT - Check Results
   ├─> Compare new UI tree with previous
   ├─> If changed: Continue loop (action succeeded)
   ├─> If unchanged: LLM may choose to retry or continue
   └─> Track execution_time_ms
   
   Step 5: LOOP or FINISH
   ├─> If task_complete: Return success
   ├─> If max_steps reached: Return failed
   └─> Else: Go to Step 1 (continue loop)
```

### Phase 3: Action Execution on Android
```
4. Android Receives Action
   ├─> HttpServer receives POST /action
   ├─> Parses JSON: Map<String, dynamic> action
   ├─> Logs: "📨 Received action from backend: {action_type}"
   └─> Calls DeviceManager.executeAction(action)

5. DeviceManager Executes Action
   ├─> Reads action_type from request
   ├─> Switch on action_type:
   │   ├─> "click"   → Get element from UI, click at coordinates
   │   ├─> "type"    → Use InputMethodManager.showSoftInput(), inject text
   │   ├─> "scroll"  → Use ScrollView.scroll() or equivalent
   │   ├─> "wait"    → Future.delayed(duration)
   │   ├─> "long_click" → Long press gesture
   │   ├─> "double_click" → Double tap gesture
   │   └─> "global_action" → AccessibilityService.performGlobalAction()
   │
   ├─> Measure execution time (start to end)
   └─> Return ActionResult with:
       {
         "action_id": "action_123",
         "success": true,
         "execution_time_ms": 145,
         "error": null
       }

6. Backend Receives Response
   ├─> ActionResult parsed from JSON response
   ├─> Logs action result (success/failure)
   ├─> Continues ReAct loop
   └─> (Next iteration: Observe new UI)
```

## Files Involved

### Backend
- **`server.py`**: FastAPI app initialization, imports device_routes
- **`routes/device_routes.py`**: HTTP endpoints for device communication
  - `GET /device/{id}/ui-tree` - Get current UI state
  - `POST /device/{id}/ui-tree` - Update UI from device
  - `POST /device/{id}/action` - Forward action to device
  - `POST /device/{id}/execute` - Alias for /action
  - `GET /device/{id}/status` - Check device status
- **`agents/execution_agent/strategies/mobile_strategy.py`**: ReAct loop
  - `execute()` - Main 5-step ReAct loop
  - `_get_ui_tree()` - HTTP GET to backend's ui-tree endpoint
  - `_execute_action_on_device()` - HTTP POST to /action or /execute
  - `_parse_action_from_response()` - Parse LLM JSON response
- **`agents/execution_agent/handlers/mobile_action_handler.py`**: Routes mobile tasks
- **`agents/coordinator_agent/coordinator_agent.py`**: Task decomposition

### Android (Flutter)
- **`lib/main.dart`**: Complete mobile app
  - `DeviceManager.registerDevice()` - POST /device/{id}/register
  - `DeviceManager.sendUITree()` - POST /device/{id}/ui-tree (periodic)
  - `DeviceManager.sendStatus()` - POST device status updates
  - `DeviceManager.executeAction()` - Execute action on device
  - `_startActionServer()` - Start HttpServer on 0.0.0.0:9999
  - Action server listener - receives POST /action requests

## Data Models

### UIAction (Sent by Backend to Android)
```python
{
    "action_id": "action_123",      # Unique ID for this action
    "action_type": "click",         # click | type | scroll | wait | long_click | double_click | global_action
    "element_id": 5,                # ID from UI tree (optional)
    "text": "username",             # For type actions
    "coordinates": [100, 200],      # For direct coordinate clicks
    "direction": "down",            # For scroll: up | down | left | right
    "duration": 500,                # For wait: milliseconds
    "x": 100, "y": 200,            # Alternative: direct x,y instead of element_id
    "global_action": "back"         # For global: back | home | recent
}
```

### ActionResult (Returned by Android to Backend)
```python
{
    "action_id": "action_123",      # Echo back the action_id
    "success": true,                # Whether action executed successfully
    "execution_time_ms": 145,       # How long action took to execute
    "error": null                   # Error message if success=false
}
```

### SemanticUITree (Sent by Android to Backend)
```python
{
    "timestamp": "2026-01-15T10:30:00Z",
    "device_id": "android_device_1",
    "elements": [
        {
            "id": 1,
            "type": "Button",
            "text": "Search",
            "clickable": true,
            "focusable": true,
            "bounds": [0, 100, 500, 200],  # [left, top, right, bottom]
            "visibility": "visible",
            "content_desc": "Search button"
        },
        ...
    ]
}
```

## Configuration & Ports

### Development (Android Emulator)
- Backend: `http://localhost:8000`
- Android from Emulator: `http://10.0.2.2:8000` (special gateway IP)
- Action Server: `http://localhost:9999` (accessible from backend)
- Backend tries: `localhost:9999` first, then falls back to `/device/{id}/execute`

### Production (Physical Device)
- Device would register with its IP address
- Backend would forward actions to `http://{device_ip}:9999/action`
- Device would post updates back to backend at `http://{backend_ip}:8000`

## Error Handling

### If Android Server Not Running
```python
# Backend falls back to /execute endpoint
# /execute endpoint returns success=false
# Mobile strategy sees failure, retries or continues based on settings
```

### If Device Offline
```python
# device["status"] == "offline"
# /execute endpoint returns immediately with success=false
# Error message: "Device is offline"
# Mobile strategy fails task or waits for device to come online
```

### If LLM Fails to Generate Action
```python
# mobile_strategy._parse_action_from_response() returns None
# Task marked as failed instead of retrying
# Error logged: "Failed to parse action from LLM response"
```

## Testing the Flow

### 1. Start Backend
```bash
cd /Users/mohammedwalidadawy/Development/YUSR/backend
python server.py
```

### 2. Start Android Emulator with AURA App
```bash
# In Android Studio or via adb
# App automatically:
# - Registers with backend
# - Starts action server on 9999
# - Sends UI tree every 2 seconds
```

### 3. Test Action Execution
```bash
cd /Users/mohammedwalidadawy/Development/YUSR
python test_action_flow.py
```

### 4. Monitor Logs
```bash
# Backend logs show:
# ✅ Device registered
# 📨 Received UI tree update
# 🎯 Sending action to device
# ✅ Action executed successfully

# Android logs show:
# 📱 Registering device with backend...
# ✅ Device registered successfully
# 📨 Received action from backend: click
# 🎬 Executing action: click
# ✅ Action executed
```

## Troubleshooting

### Actions Not Executing?
1. Check Android app is running (check logs)
2. Check action server started: "✅ Action server started on 0.0.0.0:9999"
3. Check backend receives register: "Device registered" in backend logs
4. Run `test_action_flow.py` to diagnose connections

### Device Shows Offline?
1. Android app crashed or stopped
2. Device registration failed
3. Check backend logs for "Device registered"
4. Restart Android app

### UI Tree Not Updating?
1. Android sendUITree() not being called
2. Check app permissions (Accessibility Service, etc.)
3. Check network connection between emulator and backend
4. Backend logs should show "UI tree updated"

### Slow Action Execution?
1. Check execution_time_ms in ActionResult
2. If >500ms, Android may be struggling
3. Check device CPU/memory usage
4. Reduce frequency of UI tree updates (currently every 2 seconds)

## Future Enhancements

1. **Physical Device Support**: Store device IP on registration, forward to that IP
2. **Real Action Execution**: Implement accessibility API integration
3. **Action Persistence**: Log all actions to MongoDB for analytics
4. **Multi-Device**: Support multiple devices with different task distributions
5. **Action Queueing**: Queue actions if device can't keep up
6. **Advanced Gestures**: Swipe, pinch, rotate, etc.
7. **Element Bounds Caching**: Cache element locations to speed up clicks
8. **Retry Logic**: Automatic retry on action failure with backoff
