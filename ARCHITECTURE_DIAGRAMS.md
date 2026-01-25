# ReAct Loop Architecture Diagram

## System Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                                                                            │
│                         MOBILE REACT LOOP SYSTEM                          │
│                                                                            │
└──────────────────────────────────────────────────────────────────────────┘

                              ┌─────────────────┐
                              │   GROQ LLM      │
                              │  (llama-3.3)    │
                              └────────┬────────┘
                                       │
                                  Decides Actions
                                       │
                    ┌──────────────────┴──────────────────┐
                    │                                     │
        ┌───────────▼────────────┐          ┌────────────▼──────────┐
        │      BACKEND           │          │    ANDROID DEVICE     │
        │     (FastAPI)          │          │                       │
        │                        │          │                       │
        │  ┌──────────────────┐  │          │  ┌──────────────────┐ │
        │  │ MobileReAct      │  │          │  │ ActionPolling    │ │
        │  │ Strategy         │  │          │  │ Service          │ │
        │  │                  │  │          │  │                  │ │
        │  │ • Orchestrate    │  │          │  │ • Polls backend  │ │
        │  │ • Think/Decide   │  │          │  │ • Executes acts  │ │
        │  │ • Observe        │  │          │  │ • Reports result │ │
        │  └────────┬─────────┘  │          │  └────────┬─────────┘ │
        │           │            │          │           │           │
        │  ┌────────▼─────────┐  │          │  ┌────────▼─────────┐ │
        │  │ Device Routes    │  │          │  │ ActionExecutor   │ │
        │  │                  │  │          │  │                  │ │
        │  │ • Pending-Actions│◄─┼──────────┼──┤ • Click          │ │
        │  │ • Execute-Action │─┬┼──────────┤ • Type           │ │
        │  │ • Action-Result  │◄┤┼──────────┤ • Scroll          │ │
        │  │ • UI-Tree (Get)  │  │          │ • Wait            │ │
        │  │ • UI-Tree (Post) │◄┤┼──────────┤ • Global-Action   │ │
        │  └──────────────────┘  │          │  └──────────────────┘ │
        │                        │          │                       │
        │  ┌──────────────────┐  │          │  ┌──────────────────┐ │
        │  │ Device Cache     │  │          │  │ UITreeBroadcast  │ │
        │  │                  │  │          │  │ Service          │ │
        │  │ • Device State   │  │          │  │                  │ │
        │  │ • Pending Actions│  │          │  │ • Monitors UI    │ │
        │  │ • Action Results │  │          │  │ • Sends updates  │ │
        │  │ • Cached UI Tree │  │          │  │ • On-change only │ │
        │  └──────────────────┘  │          │  └──────────────────┘ │
        │                        │          │                       │
        └────────────┬───────────┘          └───────┬────────────────┘
                     │                              │
                     │          HTTP / REST          │
                     └──────────────────────────────┘
```

---

## Detailed Component Interaction

```
┌──────────────────────────────────────────────────────────────────────────┐
│                      REACT LOOP - STEP BY STEP                           │
└──────────────────────────────────────────────────────────────────────────┘

STEP 1: OBSERVE (Get Initial UI)
─────────────────────────────────
        Backend                          Android
        ├─ GET /ui-tree ─────────────────►
                                         ├─ Fetch AccessibilityService
                                         ├─ Parse UI tree
                                         └─ Return JSON
        ◄──── UI Tree JSON ───────────────┤
        ├─ Cache UI
        └─ Pass to LLM


STEP 2: THINK (LLM Decides)
──────────────────────────────
        Backend                          Groq LLM
        ├─ Build prompt
        │  ├─ Goal: "Send message to John"
        │  ├─ UI: Current screen elements
        │  └─ History: Previous thoughts
        ├─ Call LLM ──────────────────────►
                                         ├─ Analyze
                                         └─ Generate JSON action
        ◄──── {"action_type": "click"} ───┤
        ├─ Parse response
        ├─ Extract action
        └─ Convert to UIAction


STEP 3: ACT (Execute on Device)
─────────────────────────────────
        Backend                          Android
        ├─ Queue action
        ├─ POST /pending-actions ─────────►
                                         ├─ Polling service sees it
                                         ├─ Calls ActionExecutor
                                         │  ├─ Find element
                                         │  ├─ Perform action
                                         │  └─ Measure time
                                         ├─ Build result JSON
                                         └─ POST /action-result
        ◄──── Result: success ─────────────┤
        ├─ Log execution
        └─ Verify success


STEP 4: OBSERVE (Get New UI)
─────────────────────────────
        Android                          Backend
        ├─ Screen changed!
        ├─ Parse new UI tree
        ├─ Detect screen change ID
        └─ POST /ui-tree ───────────────►
                                         ├─ Receive update
                                         ├─ Cache new state
                                         └─ Ready for next decision
        
        (Also: Polling service stores for broadcast)


LOOP CONTINUES (Go to STEP 2)
──────────────────────────────
        If goal achieved:
        ├─ LLM detects completion
        ├─ Action: "complete"
        └─ Return success
        
        If max steps reached:
        └─ Return failure: "Max steps reached"
        
        If timeout exceeded:
        └─ Return timeout
```

---

## Data Flow Diagram

```
┌────────────────────────────────────────────────────────────────────────┐
│                        DATA FLOW THROUGH SYSTEM                        │
└────────────────────────────────────────────────────────────────────────┘

                           Task Request
                                 │
                                 ▼
                    ┌──────────────────────────┐
                    │  MobileReActStrategy     │
                    │  .execute_task()         │
                    └────────┬─────────────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
              ▼                             ▼
      ┌──────────────────┐        ┌─────────────────────┐
      │ Fetch UI Tree    │        │ Initialize State    │
      │ (GET /ui-tree)   │        │ • Max steps         │
      │                  │        │ • Timeout           │
      └────────┬─────────┘        │ • History           │
               │                  └─────────────────────┘
         SemanticUITree
               │
               ▼
      ┌──────────────────────────────────┐
      │ THINK & DECIDE                   │
      │ ├─ Observation to string         │
      │ ├─ Build LLM prompt              │
      │ ├─ Call Groq API                 │
      │ ├─ Parse JSON response           │
      │ └─ Extract action                │
      └────────┬───────────────────────┬─┘
               │                       │
          JSONAction            If "complete"
               │                       │
               ├─────────────────────┬─┘
               │                     │
               ▼                     ▼
      ┌──────────────────┐   Return Success
      │ ACT: Execute     │   with metadata
      │ POST /execute-   │
      │ action           │
      └────────┬─────────┘
               │
        Android Receives
               │
               ▼
      ┌──────────────────────────────────┐
      │ Android: Action Polling          │
      │ ├─ GET /pending-actions          │
      │ ├─ Loop through actions          │
      │ ├─ Execute via ActionExecutor    │
      │ └─ POST result back              │
      └────────┬─────────────────────────┘
               │
        ActionResult (success/failure)
               │
               ▼
      ┌──────────────────────────────────┐
      │ Backend: Store & Verify          │
      │ ├─ Store in ACTION_RESULTS       │
      │ ├─ Update device state           │
      │ └─ Log execution                 │
      └────────┬─────────────────────────┘
               │
               ▼
      ┌──────────────────────────────────┐
      │ Android: Broadcast UI Tree       │
      │ ├─ Capture new screen            │
      │ ├─ Parse accessibility tree      │
      │ └─ POST /ui-tree (new state)     │
      └────────┬─────────────────────────┘
               │
        New SemanticUITree
               │
               └──────────────┐
                              │
                              ▼
                        (Loop back to THINK)
```

---

## API Endpoint Map

```
┌──────────────────────────────────────────────────────────────────────┐
│                      DEVICE ROUTES ENDPOINTS                         │
└──────────────────────────────────────────────────────────────────────┘

BACKEND ──────────────────────► ANDROID
(Orchestrator)                  (Executor)

    GET /device/{id}/pending-actions
    ◄─────────────────────────────────
         Backend queues action
         Android polls for it
         (every 1 second)

    POST /device/{id}/execute-action
    ─────────────────────────────────►
         Backend sends action
         Android receives and queues
         for execution

    POST /device/{id}/action-result
    ◄─────────────────────────────────
         Android sends back result
         Backend verifies execution

    POST /device/{id}/ui-tree
    ◄─────────────────────────────────
         Android broadcasts new UI
         Backend caches state
         (on screen change)

    GET /device/{id}/ui-tree
    ─────────────────────────────────►
         Backend fetches cached UI
         for next decision cycle
```

---

## State Transitions

```
┌──────────────────────────────────────────────────────────────────────┐
│                      STATE MACHINE / WORKFLOW                        │
└──────────────────────────────────────────────────────────────────────┘

                            START
                              │
                              ▼
                    ┌──────────────────┐
                    │ WAIT FOR DEVICE  │
                    │ Offline?         │
                    └────────┬─────────┘
                             │
                    No Error │ Yes Error
                      ┌──────┴───────┐
                      │              ▼
                      │        DEVICE OFFLINE
                      │        (return failure)
                      ▼
                ┌────────────────────────┐
                │ FETCH INITIAL UI TREE  │
                │ GET /ui-tree           │
                └────────┬───────────────┘
                         │
                    Error? ├─► FAIL
                         │
                         ▼ No
                ┌────────────────────────┐
        ┌──────►│ LOOP START             │
        │       │ Step = 1               │
        │       │ Max = N                │
        │       └────────┬───────────────┘
        │                │
        │         Check Conditions
        │         ├─ Step < Max?
        │         ├─ Time < Timeout?
        │         └─ Not Complete?
        │                │
        │        No ┌─────┴─────┐ Yes
        │          │            ▼
        │          │     ┌──────────────────────┐
        │          │     │ THINK: LLM Decides   │
        │          │     │ analyze UI + goal    │
        │          │     └────────┬─────────────┘
        │          │              │
        │          │         action = "complete"?
        │          │              │
        │          │        Yes ┌─┴──┐ No
        │          │           │    ▼
        │          │           │ ┌──────────────────┐
        │          │           │ │ ACT: Execute     │
        │          │           │ │ POST /execute    │
        │          │           │ └────────┬─────────┘
        │          │           │          │
        │          │           │     Error?
        │          │           │      ├─► Log & Continue
        │          │           │      │
        │          │           │      ▼
        │          │           │ ┌──────────────────┐
        │          │           │ │ OBSERVE: New UI  │
        │          │           │ │ GET /ui-tree     │
        │          │           │ └────────┬─────────┘
        │          │           │          │
        │          │           │      ┌───┴─────────┐
        │          │           │      │ Increment   │
        │          │           │      │ Step++      │
        │          │           └──────┴─────┬───────┘
        │          │                        │
        │          └────────────────────────┘
        │                     (loop)
        │
        └─────────────────────┐
                              │
        ┌─────────────────────┘
        │
        ▼
┌───────────────────────────┐
│ FINAL RESULT              │
├───────────────────────────┤
│ Status: success           │
│         timeout           │
│         failure           │
│ Steps: N                  │
│ Time: Nms                 │
│ Actions: [...]            │
└───────────────────────────┘
```

---

## Message Sequence Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                    MESSAGE SEQUENCE DIAGRAM                          │
└──────────────────────────────────────────────────────────────────────┘

Time    Backend                  Groq LLM        Android
│
0ms     │
        │ Start ReAct Loop
        ├─ GET /ui-tree ───────────────────────►
        │                                       │
50ms    │                                       ├─ Capture UI
        │                                       ├─ Parse tree
        │◄──────── UI Tree JSON ────────────────┤
        │
100ms   ├─ Build prompt ──────────┐
        │  (with UI context)       │
        │                          │
200ms   ├─ POST /completions ─────────────────────────►
        │                                              │
        │                                    ├─ Analyze
        │                                    ├─ Reason
300ms   │                                    ├─ Decide
        │                                    │
400ms   │◄────── Action JSON ───────────────────────────┤
        │
450ms   ├─ Verify action
        ├─ POST /execute-action ──────────────────────►
        │                                       │
500ms   │                                       ├─ Queue action
        │
        │ (User code might do polling here)
        │                                       │
550ms   │                                       ├─ GET /pending-actions
600ms   │◄─── Return queued actions ─────────────┤
        │                                       │
        │                                       ├─ Find element
        │                                       ├─ Execute action
        │                                       ├─ Measure time
650ms   │                                       │
        │                                       ├─ POST /action-result
700ms   │◄─────── Result JSON ────────────────────┤
        │
        ├─ Verify execution
750ms   │
        │                                       ├─ Screen changed!
        │                                       ├─ Parse new UI
        │                                       ├─ Detect change ID
        │                                       │
        │ (New screen detected)                 │
        │                                       ├─ POST /ui-tree
800ms   │◄──────── New UI Tree ───────────────────┤
        │
        ├─ Cache new UI
        ├─ Go to Step 2 (THINK again)
        │
850ms   │ (Loop repeats with new context)
```

---

## Component Responsibility Matrix

```
┌────────────────────────────────────────────────────────────────────────┐
│           COMPONENT RESPONSIBILITY MATRIX                              │
└────────────────────────────────────────────────────────────────────────┘

Component                  │ Orchestrate │ Decide │ Execute │ Observe
───────────────────────────┼─────────────┼────────┼─────────┼──────────
MobileReActStrategy        │     ✅      │   ✅   │    ✗    │    ✅
Device Routes              │     ✓       │   ✗    │    ✗    │    ✓
ActionPollingService       │     ✗       │   ✗    │    ✅   │    ✓
ActionExecutor             │     ✗       │   ✗    │    ✅   │    ✓
UITreeBroadcastService     │     ✗       │   ✗    │    ✗    │    ✅
Groq LLM                   │     ✗       │   ✅   │    ✗    │    ✗

Legend:
  ✅ Primary responsibility
  ✓  Supporting role
  ✗ Not involved
```

---

## Data Structure Hierarchy

```
┌────────────────────────────────────────────────────────────────────────┐
│                    DATA STRUCTURE HIERARCHY                            │
└────────────────────────────────────────────────────────────────────────┘

MobileTaskRequest
├─ task_id: str
├─ device_id: str
├─ ai_prompt: str
├─ max_steps: int
├─ timeout_seconds: int
└─ parameters: Dict

        │
        ├──► MobileReActStrategy.execute_task()
        │
        ▼

During Execution:
├─ SemanticUITree (from device)
│  ├─ screen_id: str
│  ├─ device_id: str
│  ├─ app_name: str
│  ├─ screen_name: str
│  ├─ elements: List[UIElement]
│  │  └─ UIElement
│  │     ├─ element_id: int
│  │     ├─ text: str
│  │     ├─ bounds: Bounds
│  │     └─ ...
│  └─ ...
│
├─ Dict (LLM response)
│  ├─ thought: str
│  ├─ action_type: str
│  ├─ element_id: int (optional)
│  ├─ text: str (optional)
│  └─ ...
│
├─ UIAction (converted from LLM output)
│  ├─ action_id: str
│  ├─ action_type: str
│  ├─ element_id: int (optional)
│  ├─ text: str (optional)
│  └─ ...
│
└─ ActionResult (from Android)
   ├─ action_id: str
   ├─ success: bool
   ├─ error: str (optional)
   └─ execution_time_ms: int

        │
        ▼

Final Result:
└─ MobileTaskResult
   ├─ task_id: str
   ├─ status: str ("success" | "failed" | "timeout")
   ├─ steps_taken: int
   ├─ actions_executed: List[UIAction]
   ├─ execution_time_ms: int
   ├─ error: str (optional)
   └─ completion_reason: str (optional)
```

---

**This diagram set provides a complete visual understanding of the ReAct loop system.**
