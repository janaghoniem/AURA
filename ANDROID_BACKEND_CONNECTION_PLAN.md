# Android ↔ Backend Connection Plan

## Current State Analysis

### Backend Endpoints Available (server.py):
```
POST /transcribe              - Converts audio (base64 WAV) → text
POST /process                 - Sends user input → Language Agent → Coordinator → Response
POST /text-to-speech          - Text → audio (base64 WAV)
GET  /health                  - Health check
```

### Android Current State:
- Only has MethodChannel communication (Kotlin ↔ Flutter)
- Currently isolated from backend
- Has mic button (non-functional)
- Has text field (non-functional)
- "Start Automation" button calls `AutomationService.performAutomation()` (hardcoded)

---

## Step 1: Base Connection Architecture

What we need to build:

```
┌─────────────────────────────────┐
│     Flutter UI (main.dart)      │
│  - Mic button listener          │
│  - Text input field             │
│  - Show results                 │
└──────────────┬──────────────────┘
               │
        MethodChannel
        ("com.example...")
               │
┌──────────────▼──────────────────┐
│    Kotlin Backend (MainActivity)│
│  - Record audio on mic click    │
│  - Convert to base64            │
│  - HTTP POST to /transcribe     │
│  - Receive transcribed text     │
│  - Pass to Flutter              │
└──────────────┬──────────────────┘
               │
         (Over Network)
               │
┌──────────────▼──────────────────┐
│    Python Backend (server.py)   │
│  /transcribe - Audio → Text     │
│  /process - Text → Response     │
└─────────────────────────────────┘
```

---

## Step 2: Files That Need Changes

### Backend (Python) - Minimal Changes:
1. **server.py** - ALREADY HAS endpoints, just need to enable CORS for Android
   - `/transcribe` endpoint ✅ exists
   - `/process` endpoint ✅ exists
   - CORS already enabled ✅

### Android (Kotlin/Flutter) - NEEDS Changes:

#### A. **MainActivity.kt** (Kotlin)
Add:
- HTTP client initialization
- Audio recording method that calls backend
- Receives transcribed text
- Sends transcribed text to `/process` endpoint

#### B. **main.dart** (Flutter)
Add:
- Listen to mic button taps
- Call Kotlin method to record audio
- Receive transcribed text from Kotlin
- Send text to mic field (or send directly to backend via process)
- Display results from coordinator

---

## Step 3: Data Flow (Speech to Response)

```
1. USER TAPS MIC BUTTON (Flutter)
   ↓
2. Flutter → MethodChannel → Kotlin
   (Call method: "recordAudio")
   ↓
3. Kotlin records audio → Converts to base64 WAV
   ↓
4. Kotlin HTTP POST /transcribe
   - Send: { "audio_data": "base64string", "session_id": "uuid" }
   - Receive: { "status": "success", "transcript": "text" }
   ↓
5. Kotlin → MethodChannel → Flutter
   (Receive transcribed text)
   ↓
6. Flutter shows text in mic field
   ↓
7. USER TAPS "START AUTOMATION" (or auto-submit)
   ↓
8. Flutter → MethodChannel → Kotlin
   (Call method: "sendToCoordinator" with text)
   ↓
9. Kotlin HTTP POST /process
   - Send: { "input": "text", "session_id": "uuid" }
   - Receive: { "status": "completed", "text": "response" }
   ↓
10. Kotlin → MethodChannel → Flutter
    (Receive coordinator response)
    ↓
11. Flutter displays result
```

---

## Step 4: Implementation Sequence

### Phase 1: Enable Text Input Connection
1. Add HTTP client to MainActivity.kt
2. Modify Flutter to send text from text field to backend via Kotlin
3. Receive response and display it
4. **TEST:** Type in text field → Send to backend → Get response

### Phase 2: Add Audio Recording
1. Add audio recording permissions
2. Implement audio recording in Kotlin
3. Convert audio to base64 WAV
4. Send to `/transcribe` endpoint
5. Receive transcribed text
6. **TEST:** Click mic → Record audio → Get transcribed text

### Phase 3: Connect Mic to Text Field
1. Auto-populate text field with transcribed audio
2. **TEST:** Click mic → Record → Auto-fill text field → See transcription

### Phase 4: Full Integration
1. Implement session_id tracking
2. Handle errors/timeouts
3. Add loading states
4. **TEST:** Full flow end-to-end

---

## Step 5: Code Structure Changes

### New files to create:
- `MainActivity.kt` - Add HTTP networking code (modify existing)
- No new Flutter files needed (modify existing main.dart)

### Configuration needed:
```kotlin
// In MainActivity.kt - Add constants:
const val BACKEND_URL = "http://YOUR_IP:8000"  // We'll set this up
const val NETWORK_TIMEOUT = 30000  // milliseconds
```

### Flutter Dependencies:
- `url_launcher` - Already available via Flutter/Kotlin bridge
- No new packages needed (using platform channels)

---

## Step 6: Important Details

### Backend Connection Points:

```python
# POST /transcribe
{
  "audio_data": "base64_string",    # WAV audio encoded as base64
  "session_id": "unique_id"
}

# Response:
{
  "status": "success",
  "transcript": "user text here",
  "session_id": "unique_id"
}

---

# POST /process
{
  "input": "user text or command",
  "session_id": "unique_id",
  "is_clarification": false
}

# Response:
{
  "status": "completed",
  "text": "coordinator response",
  "task_id": "optional"
}
# OR (if clarification needed):
{
  "status": "clarification_needed",
  "question": "What did you mean by..?",
  "response_id": "msg_id"
}
```

### Backend IP Configuration:
- For testing on same network: `192.168.x.x:8000` (we'll configure this)
- For cloud: `https://your-domain.com:8000`

---

## What NOT To Touch (To Avoid Breaking Backend):

❌ Don't modify:
- Language Agent logic
- Coordinator Agent logic
- Broker/Protocol structure
- Execution Agent
- AutomationService accessibility framework

✅ ONLY modify:
- MainActivity.kt (add HTTP networking)
- main.dart (add network calls)
- server.py (enable/configure CORS if needed - already done)

---

## Session Management

Important: Keep `session_id` consistent across requests:

```
1. Generate session_id on app start
2. Use same session_id for:
   - Audio transcription
   - Text processing
   - All backend requests
3. This allows backend to track conversation history
```

---

## Next Steps

1. **Confirm backend IP:** What IP/port is your backend running on?
2. **Add Kotlin HTTP code** to MainActivity.kt
3. **Connect Flutter UI** to the new Kotlin methods
4. **Test with text first** (no audio yet)
5. **Add audio recording** once text flow works
6. **End-to-end testing**

---

## Testing Strategy

```
Test 1: Backend running?
  GET http://192.168.x.x:8000/health

Test 2: Can send text?
  POST /process with "hello"

Test 3: Can get response?
  Check /process returns proper format

Test 4: Add audio later
```

---

Ready to start implementing Phase 1?
