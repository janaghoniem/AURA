import os, uuid, asyncio, json
from dotenv import load_dotenv   
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

##ADDED FOR BROKER BEGIN
import logging
from agents.utils.protocol import Channels
from agents.utils.broker import broker

logger = logging.getLogger(__name__)
##ADDED FOR BROKER END

# Removed HTTP utilities - using broker instead
# from config.settings import EXECUTION_AGENT_URL, REASONING_AGENT_URL, RL_FEEDBACK_URL
# from memory.memory_store import get_short_term_memory, get_long_term_memory
# from utils.http_utils import send_request

load_dotenv()

# --- Initialize LLM ---
from .config.settings import LLM_MODEL

llm = ChatGoogleGenerativeAI(
    model=LLM_MODEL,
    temperature=0.2,
    max_output_tokens=2048
)

# --- Memory (Simplified for broker) ---
class SimpleMemory:
    def __init__(self):
        self.entries = []
    def add(self, entry):
        self.entries.append(entry)
    def get_relevant_documents(self, query):
        return []  # Simplified - no retrieval for now

short_term_memory = SimpleMemory()
long_term_memory = SimpleMemory()

# --- Routing helpers (Now using broker instead of HTTP) ---
async def route_to_execution(task: Dict[str, Any]) -> Dict[str, Any]:
    """Send task to Execution Agent via broker"""
    logger.info(f"Routing Task to execution: {task}")
    logger.info(f"Routing to execution: {task.get('task_id')}")
    
    # Publish to broker
    await broker.publish(Channels.COORDINATOR_TO_EXECUTION, task)
    
    # For now, return pending status (actual result comes via broker callback)
    return {"status": "pending", "task_id": task.get("task_id")}

async def route_to_reasoning(task: Dict[str, Any]) -> Dict[str, Any]:
    """Send task to Reasoning Agent (not implemented yet)"""
    logger.warning(f"Reasoning agent not implemented: {task.get('task_id')}")
    return {"status": "skipped", "reason": "Reasoning agent not implemented"}

async def send_to_feedback(task: Dict[str, Any], result: Dict[str, Any]):
    """Send feedback (optional for now)"""
    logger.info(f"Feedback: {task.get('task_id')} -> {result.get('status')}")
    pass  # Implement later if needed

# --- Task Validation & Enhancement ---
class TaskSpec(BaseModel):
    """Validated task specification"""
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action: str
    context: str  # local, web, system, reasoning
    params: Dict[str, Any]
    priority: str = "normal"
    timeout: int = 30
    retry_count: int = 3
    depends_on: Optional[str] = None  # task_id of dependency

def validate_and_enhance_task(raw_task: Dict[str, Any]) -> TaskSpec:
    """
    Validates and fills missing fields in task from Language Agent.
    
    Language Agent outputs incomplete JSON with empty strings.
    This function:
    1. Generates task_id if missing/empty
    2. Sets defaults for priority, timeout, retry_count
    3. Validates required fields (action, context, params)
    """
    # Generate task_id if empty or missing
    if not raw_task.get("task_id"):
        raw_task["task_id"] = str(uuid.uuid4())
    
    # Set defaults for optional fields
    raw_task.setdefault("priority", "normal")
    raw_task.setdefault("timeout", 30)
    raw_task.setdefault("retry_count", 3)
    
    # Clean empty string values
    for key in ["priority", "timeout", "retry_count", "depends_on"]:
        if raw_task.get(key) == "":
            raw_task.pop(key, None)
    
    return TaskSpec(**raw_task)

# --- LangGraph State Management ---
class CoordinatorState(BaseModel):
    """State passed between graph nodes"""
    input: Dict[str, Any]  # Raw task from Language Agent
    plan: Optional[Dict[str, Any]] = None  # Decomposed execution plan
    results: Dict[str, Any] = Field(default_factory=dict)  # Execution results
    clarification: Optional[str] = None  # Question for Language Agent
    status: str = "pending"

# --- Orchestration Graph ---
def create_coordinator_graph():
    graph = StateGraph(dict)

    async def analyze_and_decompose(state: Dict) -> Dict:
        """
        STEP 1: Analyze incoming task and decompose into executable subtasks.
        
        REASONING:
        - Language Agent provides single-task JSON (simple commands)
        - For complex tasks, we need to break them into subtasks
        - Must identify dependencies and execution order
        - Generate unique task_ids for tracking
        """
        raw_task = state["input"]
        
        # Retrieve relevant context from long-term memory
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

        # Get LLM response
        response = await llm.ainvoke(prompt)
        response_text = response.content if hasattr(response, 'content') else str(response)
        
        # Parse JSON response
        try:
            # Remove markdown code blocks if present
            response_text = response_text.strip()
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
            
            plan = json.loads(response_text.strip())
            
            # Handle clarification needed
            if plan.get("needs_clarification"):
                return {
                    "clarification": plan["question"],
                    "status": "needs_clarification"
                }
            
            # Simple task (no decomposition)
            if not plan.get("needs_decomposition"):
                validated_task = validate_and_enhance_task(plan["enhanced_task"])
                return {
                    "plan": {
                        "parallel": [],
                        "sequential": [validated_task.dict()]
                    },
                    "status": "ready"
                }
            
            # Complex task (decomposed)
            return {
                "plan": plan,
                "status": "ready"
            }
            
        except json.JSONDecodeError as e:
            # Fallback: treat as simple task if JSON parsing fails
            logger.error(f"JSON parse error: {e}. Treating as simple task.")
            validated_task = validate_and_enhance_task(raw_task)
            return {
                "plan": {
                    "parallel": [],
                    "sequential": [validated_task.dict()]
                },
                "status": "ready"
            }

    async def execute_plan(state: Dict) -> Dict:
        """
        STEP 2: Execute the decomposed plan.
        
        REASONING:
        - Parallel tasks run concurrently (asyncio.gather)
        - Sequential tasks run in order, passing results between steps
        - Results stored in state for feedback loop
        """
        plan = state["plan"]
        results = {
            "parallel_results": [],
            "sequential_results": []
        }
        
        # Execute parallel tasks (no dependencies)
        if plan.get("parallel"):
            parallel_tasks = []
            for task in plan["parallel"]:
                if task["context"] == "reasoning":
                    parallel_tasks.append(route_to_reasoning(task))
                else:
                    parallel_tasks.append(route_to_execution(task))
            
            results["parallel_results"] = await asyncio.gather(*parallel_tasks)
        
        # Execute sequential tasks (with dependencies)
        task_outputs = {}  # Store outputs for dependency resolution
        
        for task in plan.get("sequential", []):
            # Check if task depends on previous output
            if task.get("depends_on"):
                dependency_result = task_outputs.get(task["depends_on"])
                if dependency_result:
                    # Inject previous task's output into params
                    if "input_from" in task["params"]:
                        task["params"]["input_data"] = dependency_result
            
            # Route to appropriate agent
            if task["context"] == "reasoning":
                result = await route_to_reasoning(task)
            else:
                result = await route_to_execution(task)
            
            # Store result for dependent tasks
            task_outputs[task["task_id"]] = result
            results["sequential_results"].append({
                "task_id": task["task_id"],
                "action": task["action"],
                "result": result
            })
        
        return {
            "results": results,
            "status": "executed"
        }

    async def send_feedback(state: Dict) -> Dict:
        """
        STEP 3: Send execution results to RL feedback system.
        
        REASONING:
        - Enables learning from successes/failures
        - Stores execution patterns in long-term memory
        """
        await send_to_feedback(state["input"], state["results"])
        
        # Store successful execution patterns
        if state["results"]:
            memory_entry = f"Task: {state['input'].get('action')} | Success: {len(state['results'].get('sequential_results', []))} steps"
            short_term_memory.add(memory_entry)
        
        return {"status": "completed"}

    # Build graph
    graph.add_node("analyze", analyze_and_decompose)
    graph.add_node("execute", execute_plan)
    graph.add_node("feedback", send_feedback)

    # Define edges
    graph.set_entry_point("analyze")
    
    # Conditional routing: if clarification needed, skip execution
    def route_after_analysis(state):
        if state.get("clarification"):
            return END
        return "execute"
    
    graph.add_conditional_edges("analyze", route_after_analysis)
    graph.add_edge("execute", "feedback")
    graph.add_edge("feedback", END)

    return graph.compile()

# --- Initialize Graph ---
coordinator_graph = create_coordinator_graph()

##ADDED FOR BROKER BEGIN
# --- Broker Integration ---
async def start_coordinator_agent(broker_instance):
    """Start Coordinator Agent with broker"""
    
    async def handle_task_from_language(message: dict):
        """Handle task from Language Agent"""
        logger.info(f"Coordinator received: {message.get('action')}")
        
        # Use existing coordinator_graph (NO CHANGES)
        result = await coordinator_graph.ainvoke({"input": message})

        logger.info(f"Coordinator processed task: {result.get('plan')}")
        
        # Publish tasks to execution
        if result.get("plan"):
            for task in result["plan"].get("sequential", []):
                logger.info(f"Dispatching task to Execution: {task}")
                await broker_instance.publish(Channels.COORDINATOR_TO_EXECUTION, task)
        
        # If clarification needed, send back to language
        if result.get("clarification"):
            await broker_instance.publish(Channels.COORDINATOR_OUTPUT, {
                "status": "needs_clarification",
                "question": result["clarification"]
            })
    
    async def handle_execution_result(message: dict):
        """Handle result from Execution Agent"""
        logger.info(f"Coordinator got result: {message.get('status')}")
        
        # Forward to language/user
        # await broker_instance.publish(Channels.COORDINATOR_OUTPUT, message)
    
    # Subscribe to channels
    broker_instance.subscribe(Channels.LANGUAGE_TO_COORDINATOR, handle_task_from_language)
    broker_instance.subscribe(Channels.EXECUTION_TO_COORDINATOR, handle_execution_result)
    
    logger.info("✅ Coordinator Agent started")
    
    while True:
        await asyncio.sleep(1)
##ADDED FOR BROKER END