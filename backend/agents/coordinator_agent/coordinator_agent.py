import os, uuid, asyncio, json
from dotenv import load_dotenv   
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from ..execution_agent.core import ActionStatus

import logging
from agents.utils.protocol import (
    Channels, AgentMessage, MessageType, AgentType, 
    ExecutionResult, TaskMessage
)
from agents.utils.broker import broker

logger = logging.getLogger(__name__)

load_dotenv()

# --- Initialize LLM ---
from .config.settings import LLM_MODEL

llm = ChatGoogleGenerativeAI(
    model=LLM_MODEL,
    temperature=0.1,
    max_output_tokens=2048
)

# --- Memory (Simplified for broker) ---
class SimpleMemory:
    def __init__(self):
        self.entries = []
    def add(self, entry):
        self.entries.append(entry)
    def get_relevant_documents(self, query):
        return []

short_term_memory = SimpleMemory()
long_term_memory = SimpleMemory()

# --- Task State Tracking ---
class TaskState:
    """Track state of all tasks for interruption handling"""
    def __init__(self):
        self.active_tasks: Dict[str, str] = {}  # task_id -> status
        self.plan_context: Dict[str, Any] = {}  # Current plan execution context
        self.should_stop = False
    
    def start_task(self, task_id: str):
        self.active_tasks[task_id] = "executing"
    
    def complete_task(self, task_id: str, status: str):
        self.active_tasks[task_id] = status
    
    def stop_all(self):
        self.should_stop = True
        for task_id in self.active_tasks:
            if self.active_tasks[task_id] == "executing":
                self.active_tasks[task_id] = "cancelled"
    
    def reset(self):
        self.active_tasks.clear()
        self.plan_context.clear()
        self.should_stop = False

task_state = TaskState()

# --- Task Validation & Enhancement ---
class TaskSpec(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action: str
    context: str
    params: Dict[str, Any]
    priority: str = "normal"
    timeout: Optional[int] = 30
    retry_count: Optional[int] = 2
    depends_on: Optional[str] = None
    is_root: bool = True  # NEW: Track if this is a root task or subtask


def validate_and_enhance_task(raw_task: Dict[str, Any], is_root: bool = True) -> TaskSpec:
    """Validate and enhance task with proper None/empty handling"""
    
    # Generate task_id if missing
    if not raw_task.get("task_id"):
        raw_task["task_id"] = str(uuid.uuid4())
    
    if raw_task.get("priority") in [None, "", " "]:
        raw_task["priority"] = "normal"
    
    if raw_task.get("timeout") in [None, "", " "]:
        raw_task["timeout"] = 30
    
    if raw_task.get("retry_count") in [None, "", " "]:
        raw_task["retry_count"] = 2
    
    raw_task["is_root"] = is_root
    
    # Clean up optional fields
    if raw_task.get("depends_on") in [None, "", " "]:
        raw_task.pop("depends_on", None)
    
    # Ensure timeout and retry_count are integers
    try:
        raw_task["timeout"] = int(raw_task["timeout"])
    except (ValueError, TypeError):
        raw_task["timeout"] = 30
    
    try:
        raw_task["retry_count"] = int(raw_task["retry_count"])
    except (ValueError, TypeError):
        raw_task["retry_count"] = 2
    
    return TaskSpec(**raw_task)

# --- LangGraph State Management ---
class CoordinatorState(BaseModel):
    input: Dict[str, Any]
    plan: Optional[Dict[str, Any]] = None
    results: Dict[str, Any] = Field(default_factory=dict)
    # clarification: Optional[str] = None
    status: str = "pending"
    session_id: Optional[str] = None
    original_message_id: Optional[str] = None  # Track original request
    refinement_count: int = 0  # Track how many times we've refined the plan
    completed_task_ids: List[str] = Field(default_factory=list)
    failed_tasks: List[Dict[str, Any]] = Field(default_factory=list)

# --- Plan Refinement with LLM ---
# CHANGE 14: In coordinator_agent.py - refine_plan_with_llm function

async def refine_plan_with_llm(
    original_plan: Dict[str, Any],
    failed_task: Dict[str, Any],
    error_details: str,
    context: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Ask LLM to refine the plan based on failure"""
    
    # CHANGE 14A: Extract completed task IDs
    completed_ids = context.get("completed_task_ids", [])
    
    prompt = f"""You are a task execution planner. A task in your plan failed, and you need to create an improved plan.

        # ORIGINAL PLAN
        {json.dumps(original_plan, indent=2)}

        # COMPLETED TASKS (DO NOT INCLUDE THESE IN NEW PLAN)
        {completed_ids}

        # FAILED TASK
        Task ID: {failed_task.get('task_id')}
        Action: {failed_task.get('action')}
        Context: {failed_task.get('context')}
        Action Type: {failed_task.get('params', {}).get('action_type')}
        Error: {error_details}

        # EXECUTION CONTEXT
        Completed tasks: {[t for t, s in context.get('completed_tasks', {}).items() if s == 'success']}
        Failed tasks: {[t for t, s in context.get('completed_tasks', {}).items() if s == 'failed']}

        # YOUR TASK
        Create a refined plan that:
        1. SKIPS all tasks in the "COMPLETED TASKS" list (they already succeeded)
        2. Starts from the FAILED TASK
        3. Uses alternative methods for the failed task
        4. Includes any remaining tasks after the failed one

        CRITICAL RULES:
        1. DO NOT include tasks from COMPLETED TASKS list
        2. Only include the failed task (with improvements) and any subsequent tasks
        3. Maintain dependencies correctly
        4. Use alternative action_types that are more reliable
        5. If failed task context is "reasoning" try to generate the logical task yourself
        6. Keep the same overall goal as the original plan
        7. retry_count for refined tasks should only be 1

        Common fixes:
        - If "click_element" failed: Try "press_key" or "hotkey" instead
        - If "type_text" failed: Try "hotkey" to paste or use different input method
        - If app didn't load: Add "wait_for_app" before interacting
        - If element not found: Add explicit "wait" or use different selector

        OUTPUT FORMAT: Return ONLY valid JSON with same structure:
        {{
        "needs_decomposition": true/false,
        "parallel": [],
        "sequential": [
            // ONLY include failed task + subsequent tasks
            // DO NOT include completed tasks
            // ADD PARAMETER "refined": true to failed task
        ]
        }}

        Generate the refined plan now:"""

    try:
        response = await llm.ainvoke(prompt)
        response_text = response.content if hasattr(response, 'content') else str(response)
        
        # Clean markdown
        response_text = response_text.strip()
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        
        refined_plan = json.loads(response_text.strip())
        logger.info(f"✅ LLM generated refined plan with {len(refined_plan.get('sequential', []))} tasks")
        return refined_plan
        
    except Exception as e:
        logger.error(f"❌ Plan refinement failed: {e}")
        return None

# --- Orchestration Graph ---
def create_coordinator_graph():
    graph = StateGraph(dict)

    async def analyze_and_decompose(state: Dict) -> Dict:
        """STEP 1: Analyze and decompose with root task tracking"""
        raw_task = state["input"]
        session_id = state.get("session_id")
        original_message_id = state.get("original_message_id")
        
        # Store in task state
        task_state.plan_context = {
            "session_id": session_id,
            "original_message_id": original_message_id
        }
        
        retrieved_context = long_term_memory.get_relevant_documents(
            str(raw_task.get("action", ""))
        )
        historical_context = "\n".join([doc.page_content for doc in retrieved_context]) if retrieved_context else ""
        
        # Build decomposition prompt
        prompt = f"""You are the YUSR Coordinator Agent. Decompose user tasks into executable subtasks.

        # INPUT FROM LANGUAGE AGENT
        {json.dumps(raw_task, indent=2)}

        # HISTORICAL CONTEXT
        {historical_context}

        # YOUR TASK
        Analyze the input task description and determine if the decomposition provided is enough. If not then decompose as needed, adding more tasks if needed and creating dependancies between them based on whether they're sequential or parallel:

        **SIMPLE TASK** (single action):
        - "open calculator" → Already complete, just add task_id
        - "send discord message" → Already structured correctly

        **COMPLEX TASK** (multiple steps with dependencies):
        - "check moodle assignment and create word doc with analysis"
        → Step 1: Login to Moodle (web)
        → Step 2: Extract assignment text (web) 
        → Step 3: Analyze requirements (reasoning)
        → Step 4: Generate execution plan (reasoning)
        → Step 5: Create Word doc with content (local)

        # EXECUTION CONTEXTS
        - **local**: Desktop apps (PowerPoint, Word, Calculator, Discord desktop)
        - **web**: Browser automation (Moodle login, form filling, data extraction)
        - **system**: OS commands (file operations, scripts)
        - **reasoning**: Text analysis, summarization, content generation, decision-making

        # ACTION TYPES
        - open_app: requires additional parameters "app_name" OR "exe_path"
        - click_element: requires additonal parameter "element"
        - type_text: requires additional parameter "text"
        - press_key: requires additional paramter "key"
        - hotkey: requires additional paramter "keys[]"
        - send_message: requires additional paramters "platform", "server_name", "message"
        - navigate_window: requires additional paramters "window_title", "operation"
        - file_operation: requires additional paramter "operation", "file_path"
        - inspect: requires additional paramter "window_title"

        # DEPENDENCY RULES
        - **parallel**: Independent tasks (can run simultaneously)
        - **sequential**: Dependent tasks (output of task N feeds task N+1)
        - Use "depends_on" field to reference previous task_id

        # OUTPUT FORMAT
        Return ONLY valid JSON (no markdown, no explanations):

        **For simple tasks** (no decomposition needed):
        {{
        "needs_decomposition": false,
        "enhanced_task": {{
            "task_id": "uuid",
            "action": "same as input",
            "context": "local|web|system|reasoning",
            "params": {{ /* same as input, ensure action_type exists */ }},
            "priority": "normal",
            "timeout": 30,
            "retry_count": 3
        }}
        }}

        **For complex tasks** (decomposition required - multiple steps required):
        {{
        "needs_decomposition": true,
        "parallel": [
            {{
            "task_id": "uuid-1",
            "action": "descriptive_name",
            "context": "web",
            "params": {{
                "action_type": "login",
                "url": "https://moodle.edu",
                "username": "$USER",
                "password": "$PASS"
            }},
            "priority": "high",
            "timeout": 60
            }}
        ],
        "sequential": [
            {{
            "task_id": "uuid-2",
            "action": "extract_assignment",
            "context": "web",
            "params": {{
                "action_type": "extract_data",
                "selectors": {{
                "title": ".assignment-title",
                "description": ".assignment-body"
                }}
            }},
            "depends_on": "uuid-1"
            }},
            {{
            "task_id": "uuid-3",
            "action": "analyze_requirements",
            "context": "reasoning",
            "params": {{
                "prompt": "Analyze this assignment and create execution plan",
                "input_from": "uuid-2"
            }},
            "depends_on": "uuid-2"
            }}
        ]
        }}

        **If missing critical info** (ambiguous recipient, unclear platform):
        {{
        "needs_clarification": true,
        "question": "Which Moodle course should I check? Please specify the course name."
        }}

        # CRITICAL RULES
        1. Every task MUST have unique task_id (use uuid)
        2. Execution tasks MUST include "action_type" in params
        3. Never invent information (if username unknown, use placeholder "$USER")
        4. Preserve original intent from Language Agent input
        5. For file operations, ensure paths are specific (not "desktop" but "C:\\Users\\$USER\\Desktop")

        Now analyze the input task and return ONLY the JSON response:"""

        response = await llm.ainvoke(prompt)
        response_text = response.content if hasattr(response, 'content') else str(response)
        
        try:
            response_text = response_text.strip()
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
            
            plan = json.loads(response_text.strip())
            
            if plan.get("needs_clarification"):
                return {
                    "input": state["input"],
                    "clarification": plan["question"],
                    "status": "needs_clarification",
                    "session_id": session_id,
                    "original_message_id": original_message_id
                }
            
            # Mark root tasks vs subtasks
            if not plan.get("needs_decomposition"):
                validated_task = validate_and_enhance_task(plan["enhanced_task"], is_root=True)
                return {
                    "input": state["input"],
                    "plan": {
                        "parallel": [],
                        "sequential": [validated_task.dict()]
                    },
                    "status": "ready",
                    "session_id": session_id,
                    "original_message_id": original_message_id
                }
            
            # Complex plan - mark subtasks
            for task in plan.get("sequential", []):
                task["is_root"] = False  # These are subtasks
            for task in plan.get("parallel", []):
                task["is_root"] = False

            logger.info(f"🧾 [DEBUG] Full generated task plan:\n{json.dumps(plan, indent=2)}")
            
            return {
                "input": state["input"],
                "plan": plan,
                "status": "ready",
                "session_id": session_id,
                "original_message_id": original_message_id
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            validated_task = validate_and_enhance_task(raw_task, is_root=True)
            return {
                "input": state["input"],
                "plan": {
                    "parallel": [],
                    "sequential": [validated_task.dict()]
                },
                "status": "ready",
                "session_id": session_id,
                "original_message_id": original_message_id
            }

    async def execute_plan(state: Dict) -> Dict:
        """STEP 2: Execute with failure handling and plan refinement"""
        plan = state["plan"]
        session_id = state.get("session_id")
        original_message_id = state.get("original_message_id")
        refinement_count = state.get("refinement_count", 0)
        completed_task_ids = state.get("completed_task_ids", [])

        # CHANGE 11A: Add max refinement check at start
        MAX_REFINEMENTS = 2
        if refinement_count >= MAX_REFINEMENTS:
            logger.warning(f"⚠️ Max refinements ({MAX_REFINEMENTS}) reached, will not retry further")
        
        results = {
            "parallel_results": [],
            "sequential_results": [],
            "completed_tasks": {},
            "needs_refinement": False,
            "failed_critical": None
        }
        
        # Execute parallel tasks
        if plan.get("parallel"):
            parallel_tasks = []
            for task in plan["parallel"]:
                task_state.start_task(task["task_id"])
                future = execute_single_task(task, session_id, original_message_id)
                parallel_tasks.append(future)
            
            results["parallel_results"] = await asyncio.gather(*parallel_tasks, return_exceptions=True)
        
        # Execute sequential tasks with dependency checking
        task_outputs = {}
        
        for task in plan.get("sequential", []):

            logger.info(f"🧾 [EXECUTION] Running task JSON:\n{json.dumps(task, indent=2)}")

            task_id = task.get("task_id")

            # CHANGE 13B: Skip already completed tasks
            if task_id in completed_task_ids:
                logger.info(f"⏭️ [SKIP] Task {task_id} already completed in previous attempt")
                results["completed_tasks"][task_id] = "success"
                results["sequential_results"].append({
                    "task_id": task_id,
                    "action": task["action"],
                    "result": {"status": "success", "details": "Previously completed"},
                    "skipped": True
                })
                continue

            # Check for interruption
            if task_state.should_stop:
                logger.warning("⚠️ Execution stopped by user")
                results["status"] = "cancelled"
                break
            
            # Check dependency
            if task.get("depends_on"):
                dep_status = results["completed_tasks"].get(task["depends_on"])
                if dep_status != "success":
                    logger.warning(f"⚠️ Skipping {task['task_id']} - dependency {task['depends_on']} failed")
                    task_state.complete_task(task["task_id"], "skipped")
                    results["completed_tasks"][task["task_id"]] = "skipped"
                    continue
            
            # Execute task
            task_state.start_task(task["task_id"])
            result = await execute_single_task(task, session_id, original_message_id)
            
            # Track result
            status = result.get("status", "failed")

            # NORMALIZE STATUS - handle both enum values and strings
            if status in ["success", "SUCCESS", ActionStatus.SUCCESS.value]:
                normalized_status = "success"
            elif status in ["failed", "FAILED", ActionStatus.FAILED.value]:
                normalized_status = "failed"
            else:
                normalized_status = status

            task_state.complete_task(task["task_id"], normalized_status)
            results["completed_tasks"][task["task_id"]] = normalized_status

            logger.info(f"📊 [TASK-{task['task_id'][:8]}] Status: {status} -> Normalized: {normalized_status}")

            if normalized_status == "success":
                # Task succeeded
                if task_id not in completed_task_ids:
                    completed_task_ids.append(task_id)

                task_outputs[task["task_id"]] = result
                results["sequential_results"].append({
                    "task_id": task["task_id"],
                    "action": task["action"],
                    "result": result
                })
            else:
                # Task failed - determine if critical
                is_critical = not task.get("is_root", True)
                is_refined = task.get("refined", False)

                # CHANGE 11B: Check refinement limit before triggering refinement
                if is_critical and refinement_count < MAX_REFINEMENTS and not is_refined:
                    logger.warning(f"⚠️ Critical subtask failed: {task['task_id']}, attempting refinement ({refinement_count + 1}/{MAX_REFINEMENTS})")
                    results["needs_refinement"] = True
                    results["failed_critical"] = {
                        "task": task,
                        "error": result.get("error", "Unknown error"),
                        "context": results["completed_tasks"],
                        "completed_task_ids": completed_task_ids
                    }
                    break
                else:
                    # CHANGE 11C: Report failure to user if max refinements reached
                    if refinement_count >= MAX_REFINEMENTS:
                        logger.error(f"❌ Max refinements reached. Task failed: {task['task_id']}")
                    else:
                        logger.error(f"❌ Root task failed: {task['task_id']}")
                    
                    results["sequential_results"].append({
                        "task_id": task["task_id"],
                        "action": task["action"],
                        "result": result,
                        "status": "failed",
                        "message": "Max retry attempts reached" if refinement_count >= MAX_REFINEMENTS else "Task failed"
                    })
        
        return {
            **state,
            "results": results,
            "status": "needs_refinement" if (results.get("needs_refinement") and not results.get("is_refined")) else "executed",
            "session_id": session_id,
            "original_message_id": original_message_id,
            "refinement_count": refinement_count, 
            "completed_task_ids": completed_task_ids
        }

    async def refine_and_retry(state: Dict) -> Dict:
        """STEP 3: Refine plan and retry"""
        results = state["results"]
        failed_info = results["failed_critical"]
        original_plan = state["plan"]
        refinement_count = state["refinement_count"]
        
        logger.info(f"🔄 Attempting plan refinement (attempt {refinement_count + 1}/2)")
        
        refined_plan = await refine_plan_with_llm(
            original_plan,
            failed_info["task"],
            failed_info["error"],
            failed_info["context"]
        )
        
        if refined_plan:
            return {
                **state,
                "plan": refined_plan,
                "status": "ready",
                "refinement_count": refinement_count + 1,
                "session_id": state.get("session_id"),
                "original_message_id": state.get("original_message_id"),
                "input": state["input"]
            }
        else:
            # Refinement failed - report to user
            return {
                **state,
                "status": "completed",
                "results": results,
                "session_id": state.get("session_id"),
                "original_message_id": state.get("original_message_id")
            }

    # CHANGE 9: In coordinator_agent.py - send_feedback function

    async def send_feedback(state: Dict) -> Dict:
        """STEP 4: Send results back to language agent"""
        results = state.get("results", {})
        session_id = state.get("session_id")
        original_message_id = state.get("original_message_id")
        
        # Determine if this was a subtask plan or root task
        plan = state.get("plan", {})
        is_subtask_plan = any(not t.get("is_root", True) for t in plan.get("sequential", []))
        
        # Only send to user if root task or all subtasks complete
        if not is_subtask_plan or results.get("status") != "success":
            # CHANGE 9A: Create proper response structure for TTS
            completed_count = sum(1 for s in results.get("completed_tasks", {}).values() if s == "success")
            total_count = len(results.get("completed_tasks", {}))
            
            # Build user-friendly response text
            if completed_count == total_count and total_count > 0:
                response_text = f"Task completed successfully! Executed {completed_count} steps."
            elif completed_count > 0:
                response_text = f"Partially completed: {completed_count}/{total_count} steps succeeded."
            else:
                response_text = "Task could not be completed. Please try again."
            
            # CHANGE 9B: Ensure payload structure matches what TTS expects
            response_msg = AgentMessage(
                message_type=MessageType.TASK_RESPONSE,
                sender=AgentType.COORDINATOR,
                receiver=AgentType.LANGUAGE,
                session_id=session_id,
                response_to=original_message_id,
                payload={
                    "status": "success" if completed_count > 0 else "failed",
                    "response": response_text,  # CRITICAL: Use "response" key for TTS
                    "result": {
                        "completed_tasks": results.get("completed_tasks", {}),
                        "details": results.get("sequential_results", [])
                    }
                }
            )
            
            logger.info(f"📤 [FEEDBACK] Sending to Language Agent: {response_text}")
            await broker.publish(Channels.COORDINATOR_TO_LANGUAGE, response_msg)
        
            # Store in memory
            if results:
                memory_entry = f"Task: {state['input'].get('action')} | Success: {len(results.get('sequential_results', []))} steps"
                short_term_memory.add(memory_entry)
            
            # Reset task state
            task_state.reset()
            
            return {"status": "completed"}

    # Build graph
    graph.add_node("analyze", analyze_and_decompose)
    graph.add_node("execute", execute_plan)
    graph.add_node("refine", refine_and_retry)
    graph.add_node("feedback", send_feedback)

    graph.set_entry_point("analyze")

    def route_after_analysis(state):
        if state.get("clarification"):
            return END
        return "execute"

    def route_after_execution(state):
        if state.get("status") == "needs_refinement":
            return "refine"
        return "feedback"

    graph.add_conditional_edges("analyze", route_after_analysis)
    graph.add_conditional_edges("execute", route_after_execution)
    graph.add_edge("refine", "execute")  # Retry after refinement
    graph.add_edge("feedback", END)

    return graph.compile()

async def execute_single_task(task: Dict[str, Any], session_id: str, original_message_id: str) -> Dict[str, Any]:
    """Execute a single task and wait for result"""
    
    # Create proper AgentMessage for execution
    task_msg = AgentMessage(
        message_type=MessageType.EXECUTION_REQUEST,
        sender=AgentType.COORDINATOR,
        receiver=AgentType.EXECUTION,
        session_id=session_id,
        task_id=task.get("task_id"),
        response_to=original_message_id,
        payload=TaskMessage(**task).dict()
    )
    
    logger.info(f"Routing to execution: {task.get('task_id')}")
    
    # Create future for response
    future = asyncio.Future()
    execution_futures[task.get("task_id")] = future
    
    # Publish
    await broker.publish(Channels.COORDINATOR_TO_EXECUTION, task_msg)
    
    # Wait for result
    try:
        result = await asyncio.wait_for(future, timeout=task.get("timeout", 30))
        return result
    except asyncio.TimeoutError:
        return {"status": "failed", "error": "Task timeout"}
    finally:
        execution_futures.pop(task.get("task_id"), None)

# Track pending execution results
execution_futures: Dict[str, asyncio.Future] = {}

# --- Initialize Graph ---
coordinator_graph = create_coordinator_graph()

# --- Broker Integration ---
async def start_coordinator_agent(broker_instance):
    """Start Coordinator Agent with broker"""
    
    async def handle_task_from_language(message: AgentMessage):
        """Handle task from Language Agent"""
        logger.info(f"Coordinator received: {message.payload.get('action')}")

        http_request_id = message.response_to if message.response_to else message.message_id
        
        # Extract session tracking
        state_input = {
            "input": message.payload,
            "session_id": message.session_id,
            "original_message_id": http_request_id
        }
        
        result = await coordinator_graph.ainvoke(state_input)
        logger.info(f"Coordinator processed task: {result.get('status')}")
        
        # # Send clarification if needed
        # if result.get("clarification"):
        #     clarification_msg = AgentMessage(
        #         message_type=MessageType.CLARIFICATION_REQUEST,
        #         sender=AgentType.COORDINATOR,
        #         receiver=AgentType.LANGUAGE,
        #         session_id=message.session_id,
        #         response_to=message.message_id,
        #         payload={
        #             "status": "needs_clarification",
        #             "question": result["clarification"]
        #         }
        #     )
        #     await broker_instance.publish(Channels.COORDINATOR_TO_LANGUAGE, clarification_msg)
    
    async def handle_execution_result(message: AgentMessage):
        """Handle result from Execution Agent"""
        task_id = message.task_id
        logger.info(f"Coordinator got result for {task_id}: {message.payload.get('status')}")
        
        # Resolve pending future
        if task_id in execution_futures:
            execution_futures[task_id].set_result(message.payload)
    
    # Subscribe to channels
    broker_instance.subscribe(Channels.LANGUAGE_TO_COORDINATOR, handle_task_from_language)
    broker_instance.subscribe(Channels.EXECUTION_TO_COORDINATOR, handle_execution_result)
    
    logger.info("✅ Coordinator Agent started")
    
    while True:
        await asyncio.sleep(1)