# AURA Mobile Architecture - Complete System Design

## Overview

This document describes the complete mobile automation architecture for AURA, implementing a **Hybrid Tool-Calling Architecture** using the Android Accessibility API with ReAct (Reason-Act) loops.

---

## System Architecture Diagram

```
┌────────────────────────────────────────────────────────────────┐
│                    USER VOICE COMMAND                          │
│                  (e.g., "Send the email")                      │
└─────────────────────────┬──────────────────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────────────┐
│                  LANGUAGE AGENT (Backend)                       │
│  Converts voice → text command                                 │
│  "Send the email" → NLU understanding                          │
└─────────────────────────┬──────────────────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────────────┐
│               COORDINATOR AGENT (Backend)                       │
│  Decomposes user command into sub-tasks                        │
│  Creates ActionTask(device="mobile", ai_prompt="...")          │
│  Sends ONE task at a time, waits for completion               │
└─────────────────────────┬──────────────────────────────────────┘
                          │
                          ▼
         ┌────────────────────────────────────┐
         │  Device = "mobile" ?                │
         │  (Check task.device)                │
         └────────────────────────────────────┘
                   │             │
            YES ───┘             └─── NO
                   │                  │
                   ▼                  ▼
        ┌──────────────────────┐  Desktop Strategy
        │  MOBILE STRATEGY     │  (local/web/system)
        │  (ReAct Loop)        │
        └──────────────────────┘
                   │
         ┌─────────┼─────────┐
         │         │         │
         ▼         ▼         ▼
    OBSERVE   ACT      REFLECT
      (1)     (2)        (3)
      │       │          │
      └───────┴──────────┘
              │
              └─ Loop up to 5 times or until done
              
     ┌────────────────────────────────────┐
     │    GROQ LLM (Cloud)                 │
     │  Input: Semantic UI Tree            │
     │  Output: JSON Action                │
     └────────────────────────────────────┘
              ▲
              │
              │ {
              │   "action": "click",
              │   "element_id": 1,
              │   ...
              │ }
              │
     ┌────────────────────────────────────────┐
     │    ANDROID DEVICE                      │
     │  ┌──────────────────────────────────┐  │
     │  │ AutomationService                │  │
     │  │ (Accessibility Service)          │  │
     │  │                                  │  │
     │  │ ┌────────────────────────────┐   │  │
     │  │ │ ActionExecutor             │   │  │
     │  │ │ - Executes 5 primitives:   │   │  │
     │  │ │   1. click(id)             │   │  │
     │  │ │   2. type(id, text)        │   │  │
     │  │ │   3. scroll(direction)     │   │  │
     │  │ │   4. wait(ms)              │   │  │
     │  │ │   5. global_action(action) │   │  │
     │  │ └────────────────────────────┘   │  │
     │  │                                  │  │
     │  │ ┌────────────────────────────┐   │  │
     │  │ │ UITreeParser               │   │  │
     │  │ │ - Converts accessibility   │   │  │
     │  │ │   tree to JSON             │   │  │
     │  │ │ - Semantic representation  │   │  │
     │  │ └────────────────────────────┘   │  │
     │  └──────────────────────────────────┘  │
     └────────────────────────────────────────┘
              ▲                    │
              │                    │
              │ UI Tree JSON       │ JSON Actions
              │ (50-100 tokens)    │
              │                    ▼
           HTTP API Endpoints:
           - GET /device/{id}/ui-tree
           - POST /device/{id}/execute


```

---

## File Structure

```
backend/
├── agents/
│   ├── coordinator_agent/
│   │   └── coordinator_agent.py        # Unchanged - decomposes tasks
│   ├── execution_agent/
│   │   ├── core/
│   │   │   └── exec_agent_main.py       # ← Modified: Added mobile routing
│   │   ├── strategies/
│   │   │   ├── local_strategy.py        # Desktop (unchanged)
│   │   │   ├── web_strategy.py          # Desktop (unchanged)
│   │   │   ├── system_strategy.py       # Desktop (unchanged)
│   │   │   └── mobile_strategy.py       # ← NEW: Mobile ReAct loop
│   │   ├── handlers/
│   │   │   ├── mobile_action_handler.py # ← NEW: Mobile handler
│   │   │   └── mobile_task_converter.py # ← NEW: Task conversion
│   │   └── Coordinator.py               # Unchanged - routes tasks
│   └── utils/
│       ├── device_protocol.py           # ← NEW: Shared models
│       ├── protocol.py                  # Unchanged
│       └── broker.py                    # Unchanged

android-app/
├── android/app/src/main/kotlin/
│   └── com/example/aura_project/
│       ├── AutomationService.kt         # ← Modified: Added HTTP endpoints
│       ├── ActionExecutor.kt            # ← NEW: Primitive executor
│       ├── UITreeParser.kt              # ← NEW: Tree parser
│       └── ... other files
└── lib/
    └── ... Dart files
```

---

## Key Components

### 1. Device Protocol (`device_protocol.py`)

Defines the contract for Android ↔ Backend communication:

**Request Models:**
- `SemanticUITree`: Complete UI state as JSON
- `UIAction`: Atomic action (click, type, scroll, etc.)
- `MobileTaskRequest`: Task to execute

**Response Models:**
- `ActionResult`: Result of executing an action
- `MobileTaskResult`: Final result of task execution

**Key Properties:**
```python
SemanticUITree:
  - elements: List[UIElement]
  - to_semantic_string(): Compact representation for LLM
  - screen_width, screen_height, app_name, etc.

UIAction:
  - action_type: "click" | "type" | "scroll" | "wait" | "global_action"
  - element_id, text, direction, etc. (action-specific)
  
MobileTaskRequest:
  - task_id: str
  - ai_prompt: str (natural language instruction)
  - device_id: str
  - max_steps: int (default 5)
  - timeout_seconds: int (default 30)
```

---

### 2. Android UITreeParser (`UITreeParser.kt`)

Converts Android's raw `AccessibilityNodeInfo` tree to semantic JSON.

**Input:** `AccessibilityNodeInfo` (raw accessibility tree)
**Output:** `SemanticUITree` JSON

**Example Output:**
```json
{
  "screen_id": "screen_123456",
  "device_id": "default_device",
  "app_name": "Gmail",
  "app_package": "com.google.android.gm",
  "screen_width": 1080,
  "screen_height": 2340,
  "timestamp": 1234567890.5,
  "elements": [
    {
      "element_id": 0,
      "type": "button",
      "text": "Compose",
      "content_description": "Start new email",
      "clickable": true,
      "bounds": {"left": 10, "top": 50, "right": 100, "bottom": 80},
      "visibility": "visible"
    },
    {
      "element_id": 1,
      "type": "textfield",
      "hint_text": "To:",
      "focusable": true,
      "visibility": "visible"
    },
    ...
  ]
}
```

**Benefits:**
- Only sends element metadata, not full XML
- ~50-100 tokens vs 2000+ for screenshot
- Element IDs allow precise reference
- Semantic string can be generated for compact LLM input

---

### 3. Android ActionExecutor (`ActionExecutor.kt`)

Executes the 5 primitive actions on the device.

**Primitives:**
1. **click(element_id)** - Click a button/interactive element
2. **type(element_id, text)** - Type text using clipboard paste
3. **scroll(direction)** - Scroll view (up/down/left/right)
4. **wait(duration_ms)** - Delay for UI to update
5. **global_action(action)** - System actions (HOME, BACK, RECENTS, POWER)

**Input:** `UIAction` JSON
```json
{
  "action_id": "action_123",
  "action_type": "click",
  "element_id": 5,
  "max_retries": 3
}
```

**Output:** `ActionResult` JSON
```json
{
  "action_id": "action_123",
  "success": true,
  "execution_time_ms": 234,
  "new_tree": { ... }  // Updated UI state
}
```

**Key Features:**
- Returns new UI tree after action (for ReAct reflection)
- Uses clipboard for text input (handles special chars)
- Proper error handling and logging
- Bonus actions: long_click, double_click

---

### 4. Mobile Strategy (`mobile_strategy.py`) - The ReAct Loop

**Orchestrates the observe-act-reflect loop with Groq LLM.**

```python
async def execute_task(task: MobileTaskRequest) -> MobileTaskResult:
    
    for step in range(task.max_steps):
        # 1. OBSERVE: Get current UI state
        current_tree = await self._get_ui_tree_from_device()
        
        # 2. ACT: Decide next action using Groq LLM
        next_action = await self.groq_agent.decide_next_action(
            ui_tree=current_tree,
            task_prompt=task.ai_prompt,
            previous_action=previous_action,
            action_succeeded=action_succeeded
        )
        
        # If LLM says "done", task complete
        if next_action is None:
            return MobileTaskResult(status="success", ...)
        
        # 3. REFLECT: Execute action and check if UI changed
        action_result = await self._execute_action_on_device(next_action)
        
        ui_changed = self._trees_different(current_tree, action_result.new_tree)
        
        # Update state for next iteration
        previous_action = next_action
        action_succeeded = action_result.success
    
    return MobileTaskResult(status="failed", reason="max_steps_exceeded")
```

**Key Features:**
- Groq LLM decides actions based on semantic tree
- Compact token usage (~50 tokens per loop)
- Self-correcting: tracks if actions work
- Max 5 steps prevents infinite loops
- Timeout prevents hanging

---

### 5. Groq LLM Integration (`GroqMobileAgent`)

**Uses Groq for decision-making in the ReAct loop.**

```python
class GroqMobileAgent:
    def __init__(self, model="mixtral-8x7b-32768", temperature=0.1):
        self.llm = ChatGroq(model=model, temperature=temperature)
    
    async def decide_next_action(
        self,
        ui_tree: SemanticUITree,
        task_prompt: str,
        ...
    ) -> Optional[UIAction]:
        # Convert tree to string representation
        ui_string = ui_tree.to_semantic_string()
        
        # Call Groq with instruction
        response = await self.llm.invoke([
            SystemMessage(content="You can only use 5 primitive actions..."),
            HumanMessage(content=f"UI:\n{ui_string}\n\nTask: {task_prompt}")
        ])
        
        # Parse JSON action from response
        action = self._parse_action_from_response(response.content)
        return action
```

**Token Budget:**
- Semantic UI string: ~50-100 tokens
- Task prompt: ~10-20 tokens
- System instructions: ~150 tokens
- Response (JSON action): ~30-50 tokens
- **Total per loop: ~250 tokens** (vs 2000+ for screenshot)

**Cost at Scale:**
- Task with 5 steps: ~1,250 tokens (~$0.001)
- 1000 tasks/day: ~$1
- Mixtral-8x7b is 60% cheaper than GPT-4

---

## Data Flow Example: "Send an Email"

### Step 1: User Command
```
User: "Send the email to john@example.com with subject 'Meeting'"
      ↓ Voice → Text (Language Agent)
Command: "Open Gmail compose, fill in john@example.com, subject Meeting, send"
```

### Step 2: Coordinator Decomposes
```python
ActionTask(
    task_id="task_1",
    ai_prompt="Open Gmail app and open compose",
    device="mobile",
    context="local",
    target_agent="action",
    extra_params={"max_steps": 5}
)
# Coordinator waits for task_1 to complete before sending task_2
```

### Step 3: Mobile Strategy Executes (ReAct Loop)

**Iteration 1: OBSERVE**
```
Current UI:
[0] BUTTON "Open" [CLICKABLE]
[1] BUTTON "Settings" [CLICKABLE]
[2] TEXT "Gmail Inbox"
```

**Iteration 1: ACT (Groq LLM)**
```
Input: "Open Gmail app"
LLM decides: {"action": "click", "element_id": 0}
```

**Iteration 1: REFLECT**
```
Action executed ✓
New UI:
[0] BUTTON "Compose" [CLICKABLE]
[1] TEXTFIELD "Search emails"
[2] TEXT "Gmail Compose"

UI changed? YES → Continue
```

**Iteration 2: OBSERVE**
```
Current UI:
[0] BUTTON "Compose" [CLICKABLE]
[1] TEXTFIELD "Search"
```

**Iteration 2: ACT (Groq LLM)**
```
Input: "Click Compose to open new email"
LLM decides: {"action": "click", "element_id": 0}
```

**Iteration 2: REFLECT**
```
Action executed ✓
New UI:
[0] TEXTFIELD "To:" (focusable)
[1] TEXTFIELD "Subject:" (focusable)
[2] TEXTFIELD "Body:" (focusable)
[3] BUTTON "Send" (clickable)

UI changed? YES → Continue
```

**Iteration 3: ACT**
```
Input: "Type john@example.com in the To field"
LLM decides: {"action": "type", "element_id": 0, "text": "john@example.com"}
```

**...and so on until done**

### Step 4: Task Complete

```python
MobileTaskResult(
    task_id="task_1",
    status="success",
    steps_taken=4,
    actions_executed=[
        UIAction(action_type="click", element_id=0),
        UIAction(action_type="click", element_id=0),
        UIAction(action_type="type", element_id=0, text="john@..."),
        ...
    ],
    completion_reason="Email sent successfully"
)
```

### Step 5: Coordinator Continues

Coordinator receives task_1 result, moves to next task.

---

## Critical Design Decisions

### 1. Separate Mobile Strategy (Not in Desktop Execution Agent)
**Why:** Desktop and mobile have different:
- UI automation mechanisms (file system vs app UI)
- Perception methods (screenshots vs accessibility tree)
- Action primitives (keyboard/mouse vs touch)
- Constraints (speed, power, network)

**Risk:** Modifying desktop strategy could break mobile and vice versa.

**Solution:** Completely separate `mobile_strategy.py` and `mobile_action_handler.py`.

---

### 2. ReAct Loop Inside Execution Agent (Not Coordinator)
**Why:**
- Coordinator only decomposes tasks, doesn't execute
- Mobile tasks may require retries/reflection
- Device-specific error handling belongs in device layer
- Keeps coordinator simple and focused

**Flow:**
```
Coordinator: "Here's task_1, go execute it"
              → Mobile Strategy gets it
              → Retries, reflects, self-corrects
              → Returns success/failure
Coordinator: "Got it, sending task_2"
```

---

### 3. JSON Actions Instead of Code Generation
**Why:**
- More reliable (no syntax errors)
- Versioning doesn't break old versions
- LLM only needs to output JSON (simpler)
- Easy to debug and audit
- Can be validated before execution

**Example:**
```python
# ❌ Code generation (fragile)
LLM output: "device.find(By.text('Send')).click()"

# ✅ JSON actions (robust)
LLM output: {"action": "click", "element_id": 5}
```

---

### 4. Semantic UI Tree (Not Full Screenshots)
**Why:**
- **Token efficiency:** 50-100 tokens vs 2000+ (20x reduction)
- **Cost:** $0.001 per task vs $0.05+ per screenshot
- **Latency:** Tree is instant, screenshot needs encoding
- **Clarity:** LLM focuses on structure, not pixel details

**Example:**
```
✅ Semantic (50 tokens):
[1] BUTTON "Send"
[2] TEXTFIELD "To:"
[3] TEXTFIELD "Subject:"

❌ Screenshot (2000+ tokens):
<huge base64 image data>
```

---

### 5. Groq for Mobile (Fast + Cheap)
**Why:**
- **Speed:** Mixtral-8x7b responds in ~200ms
- **Cost:** $0.14 per 1M input tokens ($0.0018 per task)
- **Quality:** Sufficient for simple UI decisions
- **Reliability:** No rate limiting for automation

**Alternative (GPT-4):**
- Speed: ~2 seconds
- Cost: $0.03 per task
- Overkill for UI automation

---

## Integration Checklist

- [x] `device_protocol.py` - Shared models
- [x] `UITreeParser.kt` - Parse accessibility tree
- [x] `ActionExecutor.kt` - Execute primitives
- [x] `mobile_strategy.py` - ReAct loop with Groq
- [x] `mobile_action_handler.py` - Handler
- [x] `exec_agent_main.py` - Routing logic
- [ ] `AutomationService.kt` - HTTP endpoints for device communication
- [ ] `main.dart` - HTTP client to communicate with backend
- [ ] `backend/routes/` - REST endpoints for device communication
- [ ] Dependency injection for device_id configuration

---

## Next Steps

1. **Add HTTP Endpoints to AutomationService:**
   - `GET /device/{id}/ui-tree` → Return current SemanticUITree
   - `POST /device/{id}/execute` → Accept UIAction, execute, return ActionResult

2. **Add HTTP Client to Flutter App:**
   - Provide device_id to backend
   - Display current task/step
   - Show UI tree visualization for debugging

3. **Add Backend Routes:**
   - `/device/{id}/ui-tree` → Forward to Android device
   - `/device/{id}/execute` → Forward action to Android device

4. **Testing:**
   - Test single action execution
   - Test ReAct loop (5 iterations)
   - Test failure and retry
   - Test timeout handling

---

## Success Metrics

- Task completion rate: >95%
- Average steps per task: <3
- Token usage per task: <1,000 (vs 5,000 for screenshots)
- Cost per task: <$0.002
- Latency per task: <15 seconds
- False failures: <5% (should be actual failures, not system issues)

---

## References

- ReAct Paper: https://arxiv.org/abs/2210.03629
- Groq Pricing: https://console.groq.com/docs/pricing
- Android Accessibility: https://developer.android.com/guide/topics/ui/accessibility/service
