#!/usr/bin/env python3
"""
language_agent.py - GROQ API VERSION

TASK COORDINATION AGENT — Llama-3.3-70b-Versatile
- Full LLM-driven conversation (no hardcoded logic)
- LLM detects vagueness and when enough info is gathered
- LLM extracts all information and creates JSON
"""

import os, re, json, uuid, time, sys
from typing import List, Dict
import asyncio
import logging
from groq import Groq # Added Groq import
from agents.utils.protocol import Channels
from agents.utils.broker import broker
from agents.utils.protocol import AgentMessage, MessageType, AgentType, ClarificationMessage
# from agents.coordinator_agent.memory.memory_store import get_memory_manager # Ensure import
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# -----------------------
# CONFIG - GROQ API (Updated)
# -----------------------
GROQ_API_KEY = os.environ.get("GROQ_API_KEY") 
MODEL_NAME = "llama-3.3-70b-versatile"  # High-performance Groq model
client = Groq(api_key=GROQ_API_KEY)

CONV_SAVE_PATH = "conversations.jsonl"
TASKS_SAVE_PATH = "tasks.jsonl"
MAX_TOKENS = 150

# -----------------------
# Utility helpers
# -----------------------
def sanitize_text(t: str) -> str:
    if not t: return ""
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"<\|[^>]+\|>", "", t)
    return t.strip()

def append_jsonl(path: str, obj: dict):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

# -----------------------
# Groq API Call (Replaces Gemini)
# -----------------------
def call_groq_api(messages: List[Dict[str, str]], max_tokens=MAX_TOKENS) -> str:
    """Call Groq API using OpenAI-compatible format"""
    if not GROQ_API_KEY:
        raise ValueError("⚠️  GROQ_API_KEY not set in .env!")
    
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.1, # Kept low for consistent task detection
            top_p=0.9,
            stream=False
        )
        text = completion.choices[0].message.content
        return sanitize_text(text)
            
    except Exception as e:
        print(f"⚠️  Groq API Error: {e}")
        return ""

# -----------------------
# System Prompts - LLM-DRIVEN (Preserved Exactly)
# -----------------------
SYSTEM_PROMPT = """You are a TASK COORDINATION AGENT. Your role is to gather information from users and prepare task instructions for execution agents.

CRITICAL RULES:
1. You do NOT execute tasks yourself - you coordinate them
2. NEVER say "I can't do X" or "I don't have the ability to X"
3. Distinguish between QUESTIONS (answer them) and TASKS (coordinate them)
4. ALWAYS use sensible defaults - NEVER ask unnecessary questions
5. When you have sufficient information, respond with EXACTLY: "TASK_COMPLETE"

GOLDEN RULE: If a reasonable default exists, USE IT. Don't ask.

QUESTION vs TASK Detection:
- "What is AI?" → QUESTION (answer it directly)
- "How do I open calculator?" → QUESTION (explain it)
- "Open calculator" → TASK (say TASK_COMPLETE immediately)
- "What's the weather?" → QUESTION (answer it)
- "Search for weather" → TASK (say TASK_COMPLETE immediately)

IMMEDIATE TASK_COMPLETE - NO QUESTIONS:
✅ "open calculator" → TASK_COMPLETE (use system default)
✅ "open notepad" → TASK_COMPLETE (use system default)
✅ "open chrome" → TASK_COMPLETE (use system default)
✅ "open word" → TASK_COMPLETE (use Microsoft Word)
✅ "open excel" → TASK_COMPLETE (use Microsoft Excel)
✅ "open file explorer" → TASK_COMPLETE (use Windows Explorer)
✅ "search for X" → TASK_COMPLETE (use Google)
✅ "play music" → TASK_COMPLETE (use default player)
✅ "open browser" → TASK_COMPLETE (use default browser)
✅ "take screenshot" → TASK_COMPLETE (use system default)

These are COMPLETE tasks. Say TASK_COMPLETE immediately. Do NOT ask:
- "Which calculator?" (there's only one system calculator)
- "Which version?" (use default)
- "Where is it installed?" (system will find it)
- "Should I close it after?" (NO, just open it)
- "Do you want to do anything else?" (NO, just the task)

ONLY Ask When TRULY Ambiguous:
❌ "download my assignment" → Which file? From where? (VAGUE - ask)
❌ "open the document" → Which document? Where? (VAGUE - ask)
❌ "send a message" → To whom? What platform? Message content? (VAGUE - ask)
❌ "create a file" → Filename? Content? Location? (VAGUE - ask)
❌ "open that file" → Which file? (VAGUE - ask)

Clear Rule:
- If it names a SPECIFIC common application → TASK_COMPLETE
- If it says "open/launch/start [APP_NAME]" → TASK_COMPLETE
- If it's missing WHICH file/document/item → Ask
- If it's missing WHERE (for downloads/saves) → Ask
- If it's missing WHO/WHAT (for messages) → Ask

Remember: 
- Answer QUESTIONS directly
- Accept named applications IMMEDIATELY (calculator, notepad, chrome, word, etc.)
- NEVER ask which version/where installed for common apps
- NEVER ask follow-up questions after opening apps
- Only ask when file/document/recipient is ambiguous"""

DECOMPOSITION_PROMPT = """Based on the conversation, create JSON task(s) following the Execution Agent API specification.

CONVERSATION:
{conversation}

CRITICAL: If the user's request involves MULTIPLE steps, create a JSON ARRAY with multiple tasks.
If it's a SINGLE step, still return an array with one task.

OUTPUT FORMAT (always an array):
[
    {{
        "task_id": "",
        "action": "brief_description",
        "context": "local/web",
        "params": {{
            "action_type": "exact_action_from_above"
        }},
        "depends_on": "",
        "priority": "",
        "timeout": null,
        "retry_count": null
    }}
]

Output ONLY the JSON array. Do not include any explanatory text before or after the JSON."""

# -----------------------
# Agent - FULL LLM DRIVEN
# -----------------------
class TaskCoordinationAgent:
    def __init__(self):
        print("="*70)
        print("🤖 TASK COORDINATION AGENT - GROQ API")
        print("="*70)
        print(f"📡 Using: {MODEL_NAME}")
        print(f"🔑 API Key: {'✓ Set' if GROQ_API_KEY else '✗ Missing'}")
        print("="*70 + "\n")
        
        self.memory = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.save_path = CONV_SAVE_PATH
        self.tasks_path = TASKS_SAVE_PATH

        self.system_prompt = {"role":"system","content":SYSTEM_PROMPT}

    def save_memory(self):
        append_jsonl(self.save_path, {
            "id": uuid.uuid4().hex,
            "timestamp": int(time.time()),
            "memory": self.memory
        })

    def check_completion(self, response: str) -> bool:
        return "TASK_COMPLETE" in response

    async def decompose_task(self, http_request_id: str):
        print("\n" + "="*70)
        print("🎯 TASK DECOMPOSITION")
        print("="*70 + "\n")
        
        conversation = "\n".join([
            f"{m['role'].upper()}: {m['content']}" 
            for m in self.memory if m['role'] in ['user', 'assistant']
        ])
        
        decomp_messages = [
            {"role": "system", "content": "You are a task decomposition expert that creates JSON tasks."},
            {"role": "user", "content": DECOMPOSITION_PROMPT.format(conversation=conversation)}
        ]
        
        print("📊 Asking Groq to analyze conversation and create JSON...")
        response = call_groq_api(decomp_messages, max_tokens=500)
        
        json_match = re.search(r'\[.*\]', response, re.DOTALL) # Changed regex to look for Array []
        if json_match:
            try:
                task = json.loads(json_match.group())
            except json.JSONDecodeError:
                task = {"error": "Invalid JSON from LLM"}
        else:
            task = {"error": "No JSON found"}

        logger.info(f"📋 Generated Task JSON: {task} ")
        task_msg = AgentMessage(
            message_type=MessageType.TASK_REQUEST,
            sender=AgentType.LANGUAGE,
            receiver=AgentType.COORDINATOR,
            response_to=http_request_id,
            payload={"tasks": task}
        )
        await broker.publish(Channels.LANGUAGE_TO_COORDINATOR, task_msg)

    def user_turn(self, user_text: str) -> tuple:
        user_text = sanitize_text(user_text)
        self.memory.append({"role": "user", "content": user_text})
        
        if len(self.memory) > 11:
            self.memory = [self.memory[0]] + self.memory[-10:]
        
        print("   🤔 Thinking...", end=" ", flush=True)
        response = call_groq_api(self.memory, max_tokens=200)
        print("✓")
        
        if not response:
            response = "I'm having trouble connecting to Groq. Please check your API key."
            return response, False
        
        is_complete = self.check_completion(response)
        display_response = response.replace("TASK_COMPLETE", "").strip()
        if not display_response and is_complete:
            display_response = "Perfect! I have all the information. Creating the task now..."
        
        self.memory.append({"role": "assistant", "content": response})
        self.save_memory()
        
        return display_response, is_complete
    
##ADDED BY JANA BEGIN
async def start_language_agent(broker):
    agent = TaskCoordinationAgent()
    
    print("="*70)
    print("🤖 TASK COORDINATION AGENT - READY (GROQ)!")
    print("="*70)
    print("Waiting for user requests...\n")
    
    async def handle_user_input(message: dict):
        # Allow passing either a dict or an AgentMessage object
        payload_data = message.payload if hasattr(message, 'payload') else message.get('payload', {})
        input_text = payload_data.get("input", "")
        
        print(f"📝 User said: {input_text}")

        user_id = payload_data.get("user_id", "default_user")
        session_id = message.session_id if hasattr(message, 'session_id') else "default_session"
        http_request_id = message.message_id if hasattr(message, 'message_id') else str(uuid.uuid4())
        

        # # NEW: Fetch Mem0 preferences for this user
        # try:
        #     from agents.coordinator_agent.memory.mem0_manager import get_preference_manager
        #     pref_mgr = get_preference_manager(user_id)
        #     preferences = pref_mgr.get_relevant_preferences(input_text, limit=5)
        #     preferences_context = pref_mgr.format_for_llm(preferences)
        #     print(f"🧠 Retrieved Mem0 Preferences:\n{preferences_context}\n")
            
        #     # FIXED: Temporarily add preferences for THIS turn only
        #     # Remove old preference entries first
        #     agent.memory = [m for m in agent.memory if not m.get("content", "").startswith("User Preferences:")]
            
        #     # Add fresh preferences at position 1 (after system prompt)
        #     if preferences and preferences_context != "No stored user preferences.":
        #         agent.memory.insert(1, {
        #             "role": "system", 
        #             "content": f"{preferences_context}"
        #         })
        # except Exception as e:
        #     logger.error(f"❌ Failed to fetch preferences: {e}")
        #     preferences_context = "No stored preferences."
        # NEW: Fetch Mem0 preferences AND conversation history for this user
        try:
            from agents.coordinator_agent.memory.mem0_manager import get_preference_manager
            pref_mgr = get_preference_manager(user_id)
            
            # Fetch both preferences and conversation history
            all_memories = pref_mgr.get_relevant_preferences(input_text, limit=10)
            
            # Separate into preferences and conversation history
            preferences = []
            conversation_history = []
            
            for memory in all_memories:
                if isinstance(memory, dict):
                    category = memory.get('metadata', {}).get('category', 'general')
                    memory_text = memory.get('memory') or memory.get('text') or str(memory)
                elif isinstance(memory, str):
                    memory_text = memory
                    category = 'general'
                else:
                    continue
                
                if 'conversation_history' in str(category):
                    conversation_history.append(memory_text)
                else:
                    preferences.append(memory_text)
            
            # Build context for LLM
            context_parts = []
            
            if preferences:
                context_parts.append("# USER PREFERENCES")
                for i, pref in enumerate(preferences[:5], 1):
                    context_parts.append(f"{i}. {pref}")
            
            if conversation_history:
                context_parts.append("\n# RECENT CONVERSATIONS")
                for i, conv in enumerate(conversation_history[:3], 1):
                    context_parts.append(f"{i}. {conv}")
            
            memory_context = "\n".join(context_parts) if context_parts else "No previous context."
            
            print(f"🧠 Retrieved Memory Context:\n{memory_context}\n")
            
            # Inject context into agent's memory
            if context_parts:
                agent.memory.insert(1, {
                    "role": "system", 
                    "content": f"Previous Context:\n{memory_context}"
                })
        except Exception as e:
            logger.error(f"❌ Failed to fetch memory: {e}")
            memory_context = "No stored context."
       

        response, is_complete = agent.user_turn(input_text)
        print(f"🤖 Agent: {response}\n")
        
        if is_complete:
            agent.memory.append({"role": "system", "content": f"user_id: {user_id}"})
            await agent.decompose_task(http_request_id=http_request_id)
        else:
            clarification_msg = AgentMessage(
                message_type=MessageType.CLARIFICATION_REQUEST,
                sender=AgentType.LANGUAGE,
                receiver=AgentType.LANGUAGE,
                session_id=session_id,
                response_to=http_request_id,
                payload={
                    "question": response,
                    "context": str(message)
                }
            )
            await broker.publish(Channels.LANGUAGE_OUTPUT, clarification_msg)
        
        if input_text.lower() in ["new chat", "start new chat", "reset conversation", "clear context"]:
            session_control_msg = AgentMessage(
                message_type=MessageType.SESSION_CONTROL,
                sender=AgentType.LANGUAGE,
                receiver=AgentType.COORDINATOR,
                session_id=session_id,
                payload={"command": "start_new_chat"}
            )
            await broker.publish(Channels.SESSION_CONTROL, session_control_msg)
            agent.memory = [{"role": "system", "content": SYSTEM_PROMPT}]
            print("Conversation reset.\n")
            return 
        
        if input_text.lower().startswith("remember that"):
            preference_text = input_text.replace("remember that", "").strip()
            pref_msg = AgentMessage(
                message_type=MessageType.STORE_PREFERENCE,
                sender=AgentType.LANGUAGE,
                receiver=AgentType.COORDINATOR,
                session_id=session_id,
                payload={"preference": preference_text, "category": "explicit"}
            )
            await broker.publish(Channels.LANGUAGE_TO_COORDINATOR, pref_msg)

    broker.subscribe(Channels.LANGUAGE_INPUT, handle_user_input)
    logger.info("✅ Language Agent started")

    while True:
        await asyncio.sleep(1)
##ADDED BY JANA END