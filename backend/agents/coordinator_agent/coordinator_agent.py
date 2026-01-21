import os, uuid, asyncio, json
from dotenv import load_dotenv   
from langgraph.graph import StateGraph, END
from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel, Field
from pymongo import MongoClient
from datetime import datetime
from collections import deque

# Imports for memory
from langgraph.checkpoint.mongodb import MongoDBSaver
from .memory.mem0_manager import get_preference_manager

import logging
from agents.utils.protocol import (
    Channels, AgentMessage, MessageType, AgentType, 
    ExecutionResult, TaskMessage
)
from agents.utils.broker import broker

logger = logging.getLogger(__name__)
load_dotenv()

# --- Initialize Groq LLM ---
from .config.settings import LLM_MODEL, GROQ_API_KEY, MONGODB_URI
from langchain_groq import ChatGroq

llm = ChatGroq(
    model=LLM_MODEL,
    temperature=0.1,
    max_tokens=2048,
    groq_api_key=GROQ_API_KEY
)

# Initialize MongoDB checkpointer
try:
    mongo_client = MongoClient(MONGODB_URI)
    mongo_client.admin.command('ping')
    checkpointer = MongoDBSaver(
        mongo_client, 
        db_name="yusr_db",
        collection_name="langgraph_checkpoints"
    )
    logger.info("✅ Initialized MongoDB checkpointer for LangGraph")
except Exception as e:
    logger.error(f"❌ Failed to initialize MongoDB checkpointer: {e}")
    checkpointer = None

# --- Task Models for RAG Action Layer ---
class ActionTask(BaseModel):
    """Task format for RAG-based action layer"""
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ai_prompt: str  # Natural language prompt for RAG LLM
    device: Literal["desktop", "mobile"]
    context: Literal["local", "web"]
    extra_params: Optional[Dict[str, Any]] = Field(default_factory=dict)
    target_agent: Literal["action", "reasoning"] = "action"
    depends_on: Optional[str] = None
    
    class Config:
        use_enum_values = True

class TaskResult(BaseModel):
    """Result from action/reasoning layer"""
    task_id: str
    status: Literal["success", "failed", "pending"]
    content: Optional[str] = None  # For reasoning agent outputs
    error: Optional[str] = None

# --- Queue Management ---
class TaskQueue:
    """Manages sequential task execution with interrupt controls"""
    def __init__(self):
        self.current_queue: deque = deque()
        self.global_queue: deque = deque()
        self.execution_history: List[Dict] = []
        self.is_paused: bool = False
        self.is_stopped: bool = False
        self.current_task_id: Optional[str] = None
        
    def add_to_current(self, tasks: List[ActionTask]):
        """Add tasks to current execution queue"""
        self.current_queue.extend(tasks)
        
    def add_to_global(self, task_plan: Dict):
        """Add new task plan to global queue"""
        self.global_queue.append(task_plan)
        
    def get_next_task(self) -> Optional[ActionTask]:
        """Get next task from current queue"""
        if self.current_queue and not self.is_paused and not self.is_stopped:
            task = self.current_queue.popleft()
            self.current_task_id = task.task_id
            return task
        return None
    
    def has_tasks(self) -> bool:
        """Check if current queue has tasks"""
        return len(self.current_queue) > 0
    
    def pause(self):
        """Pause execution"""
        self.is_paused = True
        logger.info("⏸️ Task execution paused")
        
    def resume(self):
        """Resume execution"""
        self.is_paused = False
        logger.info("▶️ Task execution resumed")
        
    def stop(self):
        """Stop and clear current queue"""
        self.is_stopped = True
        self.current_queue.clear()
        logger.info("⏹️ Task execution stopped")
        
    def reset(self):
        """Reset all flags for new task"""
        self.is_paused = False
        self.is_stopped = False
        self.current_task_id = None
        
    def log_execution(self, task: ActionTask, result: TaskResult):
        """Log task execution for undo capability"""
        self.execution_history.append({
            "task": task.dict(),
            "result": result.dict(),
            "timestamp": datetime.now().isoformat()
        })
        
    def get_failed_index(self) -> Optional[int]:
        """Get index of first failed task"""
        for idx, entry in enumerate(self.execution_history):
            if entry["result"]["status"] == "failed":
                return idx
        return None
    
    def retry_from_failed(self) -> List[ActionTask]:
        """Get tasks starting from failed one"""
        failed_idx = self.get_failed_index()
        if failed_idx is not None:
            retry_tasks = [
                ActionTask(**entry["task"]) 
                for entry in self.execution_history[failed_idx:]
            ]
            # Clear failed entries from history
            self.execution_history = self.execution_history[:failed_idx]
            return retry_tasks
        return []

# Global task queue
task_queue = TaskQueue()

# Track pending results
pending_results: Dict[str, asyncio.Future] = {}

# --- LangGraph State ---
class CoordinatorState(BaseModel):
    input: Dict[str, Any]
    plan: Optional[Dict[str, Any]] = None
    tasks: List[ActionTask] = Field(default_factory=list)
    results: Dict[str, TaskResult] = Field(default_factory=dict)
    status: str = "pending"
    session_id: Optional[str] = None
    original_message_id: Optional[str] = None
    user_id: Optional[str] = None
    preferences_context: Optional[str] = None

# --- Plan Decomposition with Groq LLM ---
async def decompose_task_to_actions(
    user_request: Dict[str, Any],
    preferences_context: str
) -> Dict[str, Any]:
    """Decompose user request into ActionTask queue using Groq LLM"""
    
    prompt = f"""You are the AURA Task Decomposition Agent. Convert user requests into low-level executable tasks.

# USER REQUEST
{json.dumps(user_request, indent=2)}

# USER PREFERENCES
{preferences_context}

============================
CORE BEHAVIOR RULES
============================

1. NEVER generate conversational, acknowledgment, confirmation, planning, preparation, or meta tasks.

❌ INVALID tasks include:
- "Confirm receipt of the request"
- "Prepare to execute the task"
- "Pass the request to another agent"
- "Wait for user input"
- "Acknowledge user command"
- "Analyze the request"
- "Decide what to do next"

✅ Every task MUST represent a real-world executable operation or a reasoning operation with concrete output.

2. Detect SIMPLE vs COMPOSITE requests:

A SIMPLE request:
- Can be completed by a single real-world action
- Has no logical sub-steps
- Has no dependencies
- Produces no intermediate artifacts

Examples:
- "Open Notepad"
- "Open Chrome"
- "Go to google.com"
- "Close Calculator"
- "Scroll down"

➜ For SIMPLE requests:
- Return EXACTLY ONE task
- DO NOT decompose
- ai_prompt must be the original user instruction verbatim or lightly normalized

A COMPOSITE request:
- Requires multiple real actions
- Produces intermediate outputs
- Has dependencies between steps
- Involves chaining reasoning + actions

Examples:
- "Download my Moodle assignment and summarize it in Notepad"
- "Find the cheapest flight and save it in a file"
- "Scrape reviews and analyze sentiment"

➜ Only COMPOSITE requests may be decomposed.

3. Always prefer the MINIMAL valid execution plan.
Never split tasks unless strictly required for execution or dependency correctness.

# YOUR TASK
Decompose the request into the SMALLEST possible tasks. Each task should be:
- A single atomic action
- Executable by either action layer (UI automation) or reasoning layer (logic/LLM)
- Clearly dependent on previous tasks when necessary

# DEVICE & CONTEXT
- **device**: "desktop" or "mobile"
- **context**: "local" (desktop apps, file system) or "web" (browser automation)

# TARGET AGENTS
- **action**: UI automation (click, type, open apps, navigate)
- **reasoning**: Logic tasks (summarize, analyze, generate content)

# TASK STRUCTURE
Each task must have:
- **ai_prompt**: Natural language instruction for RAG LLM (be specific and clear)
- **device**: "desktop" or "mobile"
- **context**: "local" or "web"
- **target_agent**: "action" or "reasoning"
- **extra_params**: Any specific data (app_name, file_path, text_to_type, url, etc.)
- **depends_on**: task_id of prerequisite task (null if independent)

# DEPENDENCY RULES
- **sequential**: Task B depends on Task A's completion (use "depends_on")
- **parallel**: Tasks can run simultaneously (no "depends_on")

============================
VALID EXAMPLES
============================

User: "Open Notepad"

Return:
[
  {
    "task_id": "task_1",
    "ai_prompt": "Open Notepad",
    "device": "desktop",
    "context": "local",
    "target_agent": "action",
    "extra_params": {"app_name": "notepad.exe"},
    "depends_on": null
  }
]

User: "Download latest Moodle assignment and summarize it to Notepad"

Tasks:
[
  {{
    "task_id": "task_1",
    "ai_prompt": "Open Chrome browser and navigate to Moodle login page",
    "device": "desktop",
    "context": "web",
    "target_agent": "action",
    "extra_params": {{"url": "https://moodle.edu"}},
    "depends_on": null
  }},
  {{
    "task_id": "task_2",
    "ai_prompt": "Download the latest assignment from Moodle",
    "device": "desktop",
    "context": "web",
    "target_agent": "action",
    "extra_params": {{}},
    "depends_on": "task_1"
  }},
  {{
    "task_id": "task_3",
    "ai_prompt": "Open the downloaded file",
    "device": "desktop",
    "context": "local",
    "target_agent": "action",
    "extra_params": {{}},
    "depends_on": "task_2"
  }},
  {{
    "task_id": "task_4",
    "ai_prompt": "Copy all content from the opened file",
    "device": "desktop",
    "context": "local",
    "target_agent": "action",
    "extra_params": {{}},
    "depends_on": "task_3"
  }},
  {{
    "task_id": "task_5",
    "ai_prompt": "Summarize the following assignment content into key points",
    "device": "desktop",
    "context": "local",
    "target_agent": "reasoning",
    "content": "<content from task_4>",
    "extra_params": {{"input_from": "task_4"}},
    "depends_on": "task_4"
  }},
  {{
    "task_id": "task_6",
    "ai_prompt": "Open Notepad application",
    "device": "desktop",
    "context": "local",
    "target_agent": "action",
    "extra_params": {{"app_name": "notepad.exe"}},
    "depends_on": "task_4"
  }},
  {{
    "task_id": "task_7",
    "ai_prompt": "Paste the summarized content into Notepad",
    "device": "desktop",
    "context": "local",
    "target_agent": "action",
    "extra_params": {{"input_from": "task_5"}},
    "depends_on": "task_5,task_6"
  }},
  {{
    "task_id": "task_8",
    "ai_prompt": "Save the file as 'assignment_summary.txt'",
    "device": "desktop",
    "context": "local",
    "target_agent": "action",
    "extra_params": {{"filename": "assignment_summary.txt"}},
    "depends_on": "task_7"
  }}
]

# CRITICAL RULES
1. **One action per task** - never combine multiple actions
2. **Explicit dependencies** - if task B needs task A's output, set "depends_on": "task_A_id"
3. **Natural prompts** - ai_prompt should be clear instructions for RAG LLM
4. **No assumptions** - if info is missing (like Moodle password), include placeholder in extra_params
5. **Parallel opportunities** - identify tasks that can run simultaneously (e.g., task_5 and task_6 above)

============================
CRITICAL CONSTRAINTS
============================

You must NEVER generate:
- setup tasks
- preparation tasks
- explanation tasks
- planning-only tasks
- acknowledgment tasks
- system-level reasoning
- descriptions of what you are doing
- clarifications or questions
- assistant-like responses

You must NEVER:
- Describe the pipeline
- Talk about agents
- Ask the user for clarification
- Explain your output

============================
OUTPUT RULES
============================

Return ONLY a valid JSON ARRAY of tasks.
No wrapping object.
No markdown.
No commentary.
No explanations.

# OUTPUT FORMAT
Return ONLY valid JSON array of tasks (no markdown, no explanations):
[
  {{
    "task_id": <string>,
    "ai_prompt": <string>,
    "device": <"desktop" | "mobile">,
    "context": <"local" | "web">,
    "target_agent": <"action" | "reasoning">,
    "extra_params": <object>,
    "depends_on": <string | null>
  }},
  ...
]
Generate the task decomposition now:"""

    try:
        response = await llm.ainvoke(prompt)
        response_text = response.content if hasattr(response, 'content') else str(response)
        response_text = response_text.strip()

        if response_text.startswith("```"):
            parts = response_text.split("```")
            response_text = parts[1] if len(parts) > 1 else response_text
            if response_text.strip().startswith("json"):
                response_text = response_text.strip()[4:]

        parsed = json.loads(response_text.strip())

        # ✅ FIX: Accept list OR wrapped object
        if isinstance(parsed, list):
            action_tasks = [ActionTask(**task) for task in parsed]
        elif isinstance(parsed, dict) and "tasks" in parsed:
            action_tasks = [ActionTask(**task) for task in parsed["tasks"]]
        else:
            raise ValueError("Invalid task decomposition format")

        logger.info(f"📋 Decomposed into {len(action_tasks)} tasks")
        return {"tasks": action_tasks}

        
    except Exception as e:
        logger.error(f"❌ Task decomposition failed: {e}")
        return {
            "error": str(e)
        }

# --- Orchestration Graph ---
def create_coordinator_graph():
    graph = StateGraph(dict)

    async def analyze_and_plan(state: Dict) -> Dict:
        """STEP 1: Decompose user request into ActionTask queue"""
        raw_task = state["input"]
        session_id = state.get("session_id")
        user_id = state.get("user_id", "default_user")
        original_message_id = state.get("original_message_id")

        # Retrieve user preferences
        try:
            pref_mgr = get_preference_manager(user_id)
            query = raw_task.get("action", "")
            preferences = pref_mgr.get_relevant_preferences(query=query, limit=5)
            preferences_context = pref_mgr.format_for_llm(preferences)
            logger.info(f"✅ Retrieved {len(preferences)} preferences for user {user_id}")
        except Exception as e:
            logger.error(f"❌ Failed to retrieve preferences: {e}")
            preferences_context = "No stored user preferences."

        # Decompose task
        plan_result = await decompose_task_to_actions(raw_task, preferences_context)
        
        tasks = plan_result.get("tasks", [])
        
        return {
            "input": state["input"],
            "tasks": tasks,
            "status": "ready",
            "session_id": session_id,
            "original_message_id": original_message_id,
            "user_id": user_id,
            "preferences_context": preferences_context,
        }

    async def execute_tasks(state: Dict) -> Dict:
        """STEP 2: Execute tasks sequentially with dependency management"""
        tasks = state["tasks"]
        session_id = state.get("session_id")
        original_message_id = state.get("original_message_id")
        
        # Add tasks to queue
        task_queue.reset()
        task_queue.add_to_current(tasks)
        
        results = {}
        task_outputs = {}  # Store outputs for dependent tasks
        
        while task_queue.has_tasks():
            # Check for stop/pause
            if task_queue.is_stopped:
                logger.warning("⏹️ Execution stopped by user")
                break
                
            while task_queue.is_paused:
                await asyncio.sleep(0.5)
            
            # Get next task
            current_task = task_queue.get_next_task()
            if not current_task:
                break
            
            # Check dependencies
            if current_task.depends_on:
                dep_ids = current_task.depends_on.split(",")
                dependencies_met = all(
                    results.get(dep_id.strip(), {}).get("status") == "success"
                    for dep_id in dep_ids
                )
                
                if not dependencies_met:
                    logger.warning(f"⏭️ Skipping {current_task.task_id} - dependencies not met")
                    results[current_task.task_id] = TaskResult(
                        task_id=current_task.task_id,
                        status="failed",
                        error="Dependency failed"
                    )
                    continue
            
            # Inject dependent task outputs
            if current_task.extra_params.get("input_from"):
                input_task_id = current_task.extra_params["input_from"]
                if input_task_id in task_outputs:
                    current_task.extra_params["input_content"] = task_outputs[input_task_id]
            
            # Execute task
            logger.info(f"🔄 Executing {current_task.task_id}: {current_task.ai_prompt[:50]}...")
            result = await execute_single_task(current_task, session_id, original_message_id)
            
            # Store result
            results[current_task.task_id] = result
            task_queue.log_execution(current_task, result)
            
            # Store output for dependent tasks
            if result.content:
                task_outputs[current_task.task_id] = result.content
            
            # Handle failure
            if result.status == "failed":
                logger.error(f"❌ Task {current_task.task_id} failed: {result.error}")
                # Option to retry from this point
                break
        
        return {
            **state,
            "results": results,
            "status": "completed",
            "session_id": session_id,
            "original_message_id": original_message_id
        }

    async def send_feedback(state: Dict) -> Dict:
        """STEP 3: Send results to Language Agent"""
        results = state.get("results", {})
        session_id = state.get("session_id")
        original_message_id = state.get("original_message_id")
        user_id = state.get("user_id", "default_user")
        
        # Count successes
        success_count = sum(1 for r in results.values() if r.status == "success")
        total_count = len(results)
        
        # Build response
        if success_count == total_count and total_count > 0:
            response_text = f"Task completed successfully! Executed {success_count} steps."
        elif success_count > 0:
            response_text = f"Partially completed: {success_count}/{total_count} steps succeeded."
        else:
            response_text = "Task could not be completed. Please try again."
        
        # Send to Language Agent
        response_msg = AgentMessage(
            message_type=MessageType.TASK_RESPONSE,
            sender=AgentType.COORDINATOR,
            receiver=AgentType.LANGUAGE,
            session_id=session_id,
            response_to=original_message_id,
            payload={
                "status": "success" if success_count > 0 else "failed",
                "response": response_text,
                "result": {
                    "completed_tasks": {k: v.status for k, v in results.items()},
                    "details": [v.dict() for v in results.values()]
                }
            }
        )
        
        logger.info(f"📤 Sending feedback: {response_text}")
        await broker.publish(Channels.COORDINATOR_TO_LANGUAGE, response_msg)
        
        # Store preferences (only on success)
        if success_count == total_count and total_count > 0:
            try:
                pref_mgr = get_preference_manager(user_id)
                
                # Extract preferences using LLM
                task_summary = {
                    "original_request": state['input'].get('action', ''),
                    "completed_steps": [t.ai_prompt for t in state['tasks']],
                    "total_steps": total_count
                }
                
                extraction_prompt = f"""Based on this completed task, extract user preferences for future tasks.

COMPLETED TASK:
{json.dumps(task_summary, indent=2)}

RULES:
- Only extract repeatable preferences (app choices, workflows, patterns)
- Ignore one-time actions
- Format as clear statements

OUTPUT FORMAT (JSON array):
[
  {{
    "preference": "User prefers Chrome for web browsing",
    "category": "app_usage",
    "confidence": "high"
  }}
]

If NO preferences, return: []

Extract now:"""

                extraction_response = await llm.ainvoke(extraction_prompt)
                extraction_text = extraction_response.content if hasattr(extraction_response, 'content') else str(extraction_response)
                
                # Clean markdown
                extraction_text = extraction_text.strip()
                if extraction_text.startswith("```"):
                    extraction_text = extraction_text.split("```")[1]
                    if extraction_text.startswith("json"):
                        extraction_text = extraction_text[4:]
                
                preferences_to_store = json.loads(extraction_text.strip())
                
                if preferences_to_store and isinstance(preferences_to_store, list):
                    for pref_obj in preferences_to_store:
                        if pref_obj.get("confidence") in ["high", "medium"]:
                            pref_mgr.add_preference(
                                pref_obj["preference"],
                                metadata={
                                    "category": pref_obj.get("category", "general"),
                                    "confidence": pref_obj.get("confidence", "medium"),
                                    "extracted_from": task_summary["original_request"]
                                }
                            )
                            logger.info(f"💾 Stored preference: {pref_obj['preference']}")
                
                # Store conversation context
                conversation_context = f"User requested: {task_summary['original_request']}. "
                conversation_context += f"Successfully completed {success_count} steps."
                
                pref_mgr.add_preference(
                    conversation_context,
                    metadata={
                        "category": "conversation_history",
                        "session_id": session_id,
                        "timestamp": datetime.now().isoformat()
                    }
                )
                
            except Exception as e:
                logger.error(f"❌ Failed to store preferences: {e}")
        
        # Check global queue
        if task_queue.global_queue:
            logger.info(f"📋 Processing next task from global queue ({len(task_queue.global_queue)} remaining)")
            # This would trigger a new graph execution
        
        return {"status": "completed"}

    # Build graph
    graph.add_node("analyze", analyze_and_plan)
    graph.add_node("execute", execute_tasks)
    graph.add_node("feedback", send_feedback)

    graph.set_entry_point("analyze")

    def route_after_analysis(state):
        return "execute"

    graph.add_conditional_edges("analyze", route_after_analysis)
    graph.add_edge("execute", "feedback")
    graph.add_edge("feedback", END)

    return graph.compile(checkpointer=checkpointer)

async def execute_single_task(
    task: ActionTask,
    session_id: str,
    original_message_id: str
) -> TaskResult:
    """Execute a single task via action/reasoning layer"""
    
    # Route to appropriate agent
    if task.target_agent == "action":
        channel = Channels.COORDINATOR_TO_EXECUTION
        receiver = AgentType.EXECUTION
    else:
        channel = Channels.COORDINATOR_TO_REASONING
        receiver = AgentType.REASONING
    
    # Create message
    task_msg = AgentMessage(
        message_type=MessageType.EXECUTION_REQUEST,
        sender=AgentType.COORDINATOR,
        receiver=receiver,
        session_id=session_id,
        task_id=task.task_id,
        response_to=original_message_id,
        payload=task.dict()
    )
    
    # Create future for response
    future = asyncio.Future()
    pending_results[task.task_id] = future
    
    # Publish
    await broker.publish(channel, task_msg)
    
    # Wait for result
    try:
        result_payload = await asyncio.wait_for(future, timeout=60)
        return TaskResult(**result_payload)
    except asyncio.TimeoutError:
        return TaskResult(
            task_id=task.task_id,
            status="failed",
            error="Task timeout"
        )
    finally:
        pending_results.pop(task.task_id, None)

# Initialize graph
coordinator_graph = create_coordinator_graph()

# --- Broker Integration ---
async def start_coordinator_agent(broker_instance):
    """Start Coordinator Agent with broker"""
    
    async def handle_task_from_language(message: AgentMessage):
        """Handle task from Language Agent"""
        logger.info(f"📨 Coordinator received: {message.payload.get('action', 'Unknown')}")

        http_request_id = message.response_to if message.response_to else message.message_id
        user_id = message.payload.get("user_id", "default_user")
        
        # Check if this is a new task while executing
        if task_queue.has_tasks() and not task_queue.is_stopped:
            logger.info("📥 Adding task to global queue (currently executing)")
            task_queue.add_to_global(message.payload)
            return
        
        # Execute task
        state_input = {
            "input": message.payload,
            "session_id": message.session_id,
            "original_message_id": http_request_id,
            "user_id": user_id
        }
        config = {
            "configurable": {
                "thread_id": message.session_id,
                "user_id": user_id
            }
        }

        result = await coordinator_graph.ainvoke(state_input, config)
        logger.info(f"✅ Task processing complete: {result.get('status')}")
    
    async def handle_action_result(message: AgentMessage):
        """Handle result from Action/Reasoning layer"""
        task_id = message.task_id
        logger.info(f"📬 Result for {task_id}: {message.payload.get('status')}")
        
        # Resolve pending future
        if task_id in pending_results:
            pending_results[task_id].set_result(message.payload)
    
    async def handle_interrupt_command(message: AgentMessage):
        """Handle pause/stop/resume commands"""
        command = message.payload.get("command")
        
        if command == "pause":
            task_queue.pause()
        elif command == "resume":
            task_queue.resume()
        elif command == "stop":
            task_queue.stop()
        elif command == "retry":
            # Retry from last failed task
            retry_tasks = task_queue.retry_from_failed()
            if retry_tasks:
                task_queue.add_to_current(retry_tasks)
                task_queue.resume()
                logger.info(f"🔄 Retrying from failed task ({len(retry_tasks)} tasks)")
        
        # Send acknowledgment
        ack_msg = AgentMessage(
            message_type=MessageType.TASK_RESPONSE,
            sender=AgentType.COORDINATOR,
            receiver=AgentType.LANGUAGE,
            session_id=message.session_id,
            response_to=message.message_id,
            payload={"status": "acknowledged", "command": command}
        )
        await broker_instance.publish(Channels.COORDINATOR_TO_LANGUAGE, ack_msg)
    
    async def handle_session_control(message: AgentMessage):
        """Handle session reset"""
        command = message.payload.get("command")
        session_id = message.session_id
        
        if command == "start_new_chat":
            try:
                await checkpointer.aput(
                    config={"configurable": {"thread_id": session_id}},
                    checkpoint=None,
                    metadata={"cleared": True}
                )
                logger.info(f"🗑️ Cleared session history for {session_id}")
            except Exception as e:
                logger.error(f"❌ Failed to clear session: {e}")

            confirm_msg = AgentMessage(
                message_type=MessageType.TASK_RESPONSE,
                sender=AgentType.COORDINATOR,
                receiver=AgentType.LANGUAGE,
                session_id=session_id,
                response_to=message.message_id,
                payload={
                    "status": "Success",
                    "response": "Started a new conversation. Previous session memory cleared."
                }
            )
            await broker_instance.publish(Channels.COORDINATOR_TO_LANGUAGE, confirm_msg)
    
    # Subscribe to channels
    broker_instance.subscribe(Channels.LANGUAGE_TO_COORDINATOR, handle_task_from_language)
    broker_instance.subscribe(Channels.EXECUTION_TO_COORDINATOR, handle_action_result)
    broker_instance.subscribe(Channels.REASONING_TO_COORDINATOR, handle_action_result)
    broker_instance.subscribe(Channels.INTERRUPT_CONTROL, handle_interrupt_command)
    broker_instance.subscribe(Channels.SESSION_CONTROL, handle_session_control)
    
    logger.info("✅ Coordinator Agent started with RAG action layer support")
    
    while True:
        await asyncio.sleep(1)