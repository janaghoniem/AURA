# Android ↔ Backend Connection - TESTING GUIDE

## ✅ What We Just Implemented

### Kotlin Changes (MainActivity.kt)
- ✅ Added HTTP client networking
- ✅ Backend URL: `http://10.0.2.2:8000` (Android emulator → host machine)
- ✅ New method: `sendTextToCoordinator(text: String)` 
- ✅ New MethodChannel call: `"sendTextToBackend"` - sends text to backend

### Flutter Changes (main.dart)
- ✅ Text field now editable with `TextEditingController`
- ✅ "Start Automation" button now sends text to backend
- ✅ Response from backend displayed in UI
- ✅ Loading indicator while waiting for response
- ✅ Error handling and display
- ✅ Session ID tracking (unique per app run)

---

## 🚀 How to Test

### Step 1: Ensure Backend is Running
```bash
cd /Users/mohammedwalidadawy/Development/YUSR/backend
python server.py
```
Should show:
```
Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### Step 2: Build and Run Android App
```bash
cd /Users/mohammedwalidadawy/Development/YUSR/android-app
flutter run
```

### Step 3: Test Text Flow

**In the app:**
1. Type in the text field: `"hello"` or `"send email"`
2. Tap "Start Automation" button
3. Wait for response (should show in green box below status)
4. Check backend logs for incoming request

**Expected in backend logs:**
```
📥 HTTP request from session xxx: hello
📋 Created task request message
💬 Payload: {'input': 'hello'}
📤 Publishing message to language.input
⏰ Waiting up to 60s for response...
✅ Response received
```

**Expected in app:**
- Status changes to "Sending to backend..."
- Then "Response received!"
- Response text appears in box below status

---

## 🔧 Data Flow Diagram

```
User types "hello" in text field
         ↓
User taps "Start Automation"
         ↓
Flutter calls: platform.invokeMethod('sendTextToBackend', {'text': 'hello'})
         ↓
Kotlin (MainActivity) receives call
         ↓
Creates JSON: {"input": "hello", "session_id": "uuid", "is_clarification": false}
         ↓
POST to http://10.0.2.2:8000/process
         ↓
Backend receives request
         ↓
Language Agent processes "hello"
         ↓
Coordinator Agent routes and responds
         ↓
Backend returns JSON response
         ↓
Kotlin receives response
         ↓
Extracts message and returns to Flutter
         ↓
Flutter displays response in green box
```

---

## 📱 UI Changes

### Text Field
- Now: **EDITABLE** ✅
- Placeholder: "Enter text or command"
- Accepts any user input

### "Start Automation" Button
- Now: **FUNCTIONAL** ✅
- Sends text to backend instead of just local automation
- Shows loading indicator while waiting
- Disables input while loading

### Mic Button
- Status: Disabled (grayed out) for now
- Will be enabled in Phase 2 (audio recording)

### Response Display
- New: Green box appears below status
- Shows coordinator's response text
- Updates on every submission

---

## 🐛 Troubleshooting

### Issue: "Connection refused" error
**Solution:**
- Ensure backend is running: `python server.py`
- Check backend shows: `Uvicorn running on http://0.0.0.0:8000`
- Ensure emulator can reach host (sometimes needs network settings adjustment)

### Issue: App shows loading forever
**Solution:**
- Check backend logs - is it receiving the request?
- Verify backend endpoint is actually `/process` not something else
- Check if Language Agent is running (should log "✅ Language Agent started")

### Issue: Text appears to send but no response
**Solution:**
- Check backend logs for errors
- Look for Language Agent output
- Coordinator Agent should log processing

### Issue: Emulator can't connect to backend
**Solution:**
- In emulator, backend IP is NOT localhost
- Use: `http://10.0.2.2:8000` (already set in code)
- Or: Get your Mac's local IP and use that
  ```bash
  ifconfig | grep "inet " | grep -v 127.0.0.1
  ```

---

## ✨ What's Working Now

✅ Android app can connect to backend
✅ Text input is functional
✅ Sends text to Language Agent via Coordinator
✅ Receives response and displays it
✅ Session tracking across requests
✅ Error handling and display
✅ Loading states

---

## 📝 Next Steps (After Testing)

### Phase 2: Audio Recording
1. Add microphone permission to AndroidManifest.xml
2. Implement audio recording on Kotlin side
3. Convert audio to base64 WAV
4. Call `/transcribe` endpoint
5. Auto-populate text field with transcribed text

### Phase 3: Automation Execution
1. Parse coordinator response for actions
2. Route to AndroidStrategy in backend
3. Backend sends back automation tasks as JSON
4. Execute tasks dynamically in AutomationService

---

## 🎯 Test Commands

### Quick Test - Send "hello"
Text field: `hello`
Expected: Coordinator responds with something like "Hi! How can I help?"

### Test with Command
Text field: `send email to john`
Expected: Coordinator might ask clarifying questions or prepare task

### Test with Question
Text field: `what can you do?`
Expected: Coordinator explains capabilities

---

## 📊 What's Being Tracked

**Session ID:** Generated on app start, same for entire session
- Example: `550e8400-e29b-41d4-a716-446655440000`

**Each request includes:**
- `session_id` - for conversation history
- `input` - user's text
- `is_clarification` - whether it's a clarification response

**Response includes:**
- `status` - "completed" or "clarification_needed"
- `text` or `question` - the response
- `task_id` - for tracking

---

## ⚠️ Important Notes

- **Backend URL:** `http://10.0.2.2:8000` is hardcoded for emulator
  - If using real phone on network, change to: `http://192.168.x.x:8000` (your Mac's IP)
  - If using cloud backend, change to: `https://your-domain.com:8000`

- **Session ID:** Unique per app run
  - New session every time app restarts
  - Good for testing, but in production might want persistent sessions

- **Network Timeout:** 30 seconds
  - If backend is slow, response might timeout
  - Increase `NETWORK_TIMEOUT` constant in MainActivity.kt if needed

---

## 🎬 Recording of Test Session

When you test, save the output:

**Terminal 1 - Backend logs:**
```
Copy relevant lines from backend console
```

**Terminal 2 - Emulator logs (optional):**
```
flutter logs
```

**App Screenshots:**
- Before sending: Show text field with input
- After sending: Show response displayed
- Errors if any

---

**Ready to test? Let me know the results!**
