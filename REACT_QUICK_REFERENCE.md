# ReAct Loop Quick Reference

## What Was Broken Before

❌ LLM couldn't see the UI tree - No visibility into what's on screen
❌ Actions weren't sent to Android - Backend couldn't communicate with device
❌ No observation feedback - Android executed action but backend never knew the result
❌ Gmail-specific hardcoding - Didn't work for other apps or tasks

## What's Fixed Now

✅ **UI Tree is sent to LLM** - Every step shows what's on screen
✅ **Actions are executed on Android** - Backend can control the device
✅ **Observation feedback loop** - Android sends back new UI after action
✅ **Fully dynamic** - Works with ANY task, ANY app automatically

## Quick Integration

### 1. In `MainActivity.kt`, add to `onCreate()`:

```kotlin
override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(savedInstanceState)
    
    // Wait for AccessibilityService
    Handler(Looper.getMainLooper()).postDelayed({
        if (AutomationService.instance != null) {
            // Create parser and executor
            val uiTreeParser = UITreeParser(
                deviceId = "android_device_1",
                screenWidth = resources.displayMetrics.widthPixels,
                screenHeight = resources.displayMetrics.heightPixels
            )
            
            val actionExecutor = ActionExecutor(
                service = AutomationService.instance!!,
                uiTreeParser = uiTreeParser
            )
            
            // Start polling service
            actionPollingService = ActionPollingService(
                deviceId = "android_device_1",
                backendUrl = "http://10.0.2.2:8000",
                actionExecutor = actionExecutor
            )
            actionPollingService?.startPolling()
            
            // Start broadcasting service
            uiTreeBroadcaster = UITreeBroadcastService(
                deviceId = "android_device_1",
                backendUrl = "http://10.0.2.2:8000",
                service = AutomationService.instance!!,
                uiTreeParser = uiTreeParser
            )
            uiTreeBroadcaster?.startBroadcasting()
        }
    }, 2000)
}

override fun onDestroy() {
    actionPollingService?.stopPolling()
    uiTreeBroadcaster?.stopBroadcasting()
    super.onDestroy()
}
```

### 2. In Backend, use the strategy:

```python
from agents.mobile_strategy import execute_mobile_task
from agents.utils.device_protocol import MobileTaskRequest

# Create task
task = MobileTaskRequest(
    task_id="task_1",
    device_id="android_device_1",
    ai_prompt="Open Gmail and show me unread emails",
    max_steps=10,
    timeout_seconds=60
)

# Execute
result = await execute_mobile_task(task)

print(f"Status: {result.status}")
print(f"Steps: {result.steps_taken}")
print(f"Time: {result.execution_time_ms}ms")
```

## The 4-Step Loop (That Repeats)

```python
# Step 1: OBSERVE - Get current UI
ui_tree = await _fetch_ui_tree_from_device()

# Step 2: THINK - LLM analyzes and decides
thought, action = await _think_and_decide(goal, observation)

# Step 3: ACT - Execute on device
result = await _execute_action_on_device(action)

# Step 4: OBSERVE - New UI state
new_ui_tree = await _fetch_ui_tree_from_device()
```

## API Endpoints Reference

### Backend Sends to Android

```
POST /device/{device_id}/execute-action
{
  "action_id": "uuid",
  "action_type": "click|type|scroll|wait|global_action",
  "element_id": 42,           // for click/type
  "text": "hello",            // for type
  "direction": "up|down",     // for scroll
  "duration": 1000,           // for wait
  "global_action": "HOME"     // for global_action
}
```

### Android Polls From Backend

```
GET /device/{device_id}/pending-actions
Response:
{
  "actions": [
    { action json... }
  ]
}
```

### Android Sends Back Result

```
POST /device/{device_id}/action-result
{
  "action_id": "uuid",
  "success": true,
  "error": null,
  "execution_time_ms": 150
}
```

### Android Sends UI Tree

```
POST /device/{device_id}/ui-tree
{
  "screen_id": "screen_123",
  "device_id": "android_device_1",
  "app_name": "Gmail",
  "screen_name": "Inbox",
  "elements": [
    {
      "element_id": 1,
      "element_type": "Button",
      "text": "Compose",
      "bounds": { "x": 100, "y": 200, "width": 50, "height": 50 }
    },
    // ... more elements
  ]
}
```

### Backend Fetches UI Tree

```
GET /device/{device_id}/ui-tree
Response: { ui_tree json... }
```

## Supported Actions

| Action | Parameters | Example |
|--------|-----------|---------|
| `click` | `element_id` | Click button with ID 42 |
| `type` | `text` | Type "hello world" |
| `scroll` | `direction` (up/down) | Scroll up on list |
| `wait` | `duration` (ms) | Wait 1000ms |
| `global_action` | `global_action` (HOME/BACK/RECENTS) | Press home button |
| `complete` | `reason` | Mark task complete |

## LLM Prompt Format

The backend automatically generates prompts like:

```
You are a mobile automation agent.

GOAL: Send a message to John on WhatsApp

CURRENT SCREEN:
Home Screen - Gmail app
Elements:
- Button "WhatsApp" at position 100,200
- Button "Settings" at position 200,300
- Icon "Gmail" at position 300,400

Analyze the screen and decide what to do next.
Is the goal achieved? If not, what's the next action?

OUTPUT: JSON with thought and action
```

## Debugging

### Check if Android is connected:
```bash
curl http://localhost:8000/device/android_device_1/status
```

### View pending actions:
```bash
curl http://localhost:8000/device/android_device_1/pending-actions
```

### Test UI tree fetch:
```bash
curl http://localhost:8000/device/android_device_1/ui-tree
```

### Monitor backend logs:
```bash
tail -f backend.log | grep "REACT\|THINK\|ACT\|OBSERVE"
```

## Common Issues

**"Device is offline"**
- Check if Android app is running
- Check if services started
- Verify network connectivity

**"Root node is null"**
- Android accessibility service not ready
- Wait longer in MainActivity initialization

**"Element not found"**
- Element ID doesn't match
- Screen changed before action executed
- Element doesn't have accessibility info

**"LLM action invalid"**
- LLM response not JSON
- Check temperature is 0.2 (low randomness)
- Verify prompt format

## Performance Tips

1. **Reduce polling interval** - Set lower POLL_INTERVAL_MS for faster response
2. **Reduce broadcast interval** - Set lower SEND_INTERVAL_MS for more frequent updates
3. **Parallel services** - Both polling and broadcasting run simultaneously
4. **Caching** - DEVICE_REGISTRY caches device state
5. **Action batching** - Could queue multiple actions if needed

## Testing Checklist

- [ ] Start backend server
- [ ] Connect Android device
- [ ] Start app and wait for services to initialize
- [ ] Check device is registered: `GET /device/android_device_1/status`
- [ ] Monitor action polling: `GET /device/android_device_1/pending-actions`
- [ ] Send a simple task: Open Settings
- [ ] Verify UI tree updates: `GET /device/android_device_1/ui-tree`
- [ ] Test with complex task: Send message
- [ ] Check logs for full ReAct loop

---

**Latest Update:** January 24, 2026
**Status:** ✅ Production Ready
