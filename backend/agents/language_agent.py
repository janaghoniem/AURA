#!/usr/bin/env python3
"""
language_agent.py - GROQ API VERSION - FIXED JSON PARSING
"""

import os, re, json, uuid, time, sys
from typing import List, Dict
import asyncio
import logging
from groq import Groq
from typing import List, Dict
from agents.utils.protocol import Channels
from agents.utils.broker import broker
from agents.utils.protocol import AgentMessage, MessageType, AgentType, ClarificationMessage
from dotenv import load_dotenv
from ThinkingStepManager import ThinkingStepManager

load_dotenv()
logger = logging.getLogger(__name__)

# -----------------------
# CONFIG - GROQ API
# -----------------------
GROQ_API_KEY = os.environ.get("GROQ_API_KEY") 
MODEL_NAME = "llama-3.3-70b-versatile"
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
# Groq API Call
# -----------------------
def call_groq_api(messages: List[Dict[str, str]], max_tokens=MAX_TOKENS) -> str:
    if not GROQ_API_KEY:
        raise ValueError("⚠️  GROQ_API_KEY not set in .env!")
    
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.1,
            top_p=0.9,
            stream=False
        )
        text = completion.choices[0].message.content
        return sanitize_text(text)
            
    except Exception as e:
        print(f"⚠️  Groq API Error: {e}")
        return ""

# -----------------------
# SYSTEM PROMPT
# -----------------------
SYSTEM_PROMPT = """You are a Conversational Clarity Agent. Your role is to determine if a user's request is a "Question" (to be answered) or a "Task" (to be executed).

### CORE PRINCIPLE
Ask clarification questions ONLY when missing information makes task execution impossible. If reasonable defaults exist or the task can proceed without the information, mark it complete immediately.

### CRITICAL INFORMATION TEST
Before asking ANY question, verify:
1. Can the task be executed without this information? → If YES, use defaults and mark complete
2. Is there a system/contextual default available? → If YES, use it and mark complete
3. Would the task fail completely without this specific detail? → If NO, mark complete

### DECISION LOGIC
**IF user input is a QUESTION** (e.g., "What is X?", "How do I Y?"):
- Answer briefly and set is_complete: false

**IF user input is a TASK**:
- **COMPLETE** if ANY of these are true:
  - Specific app/file/action is named (e.g., "Open Word", "summarize report.pdf")
  - Common defaults exist (e.g., "open browser" → default browser)
  - Task has all minimum required parameters (see below)
  - Ambiguity doesn't prevent execution (e.g., "take a screenshot" needs no clarification)

- **INCOMPLETE** if ALL of these are true:
  - Missing information makes execution impossible (not just suboptimal)
  - No reasonable default exists
  - No context clues provide the missing detail
  
  Then ask ONE specific question about the blocking parameter only.

### MINIMUM REQUIRED PARAMETERS BY TASK TYPE
- **Open/Launch**: App name OR default exists (e.g., "browser" → Chrome/Edge)
- **File operations** (read/edit/summarize): Specific filepath OR single obvious file in context
- **Communication** (send/email): Recipient AND message content (platform can default)
- **Search**: Search query (engine can default to Google)
- **Create/Write**: What to create (location can default to Desktop/Documents)
- **System actions** (screenshot/alarm/reminder): Action itself (parameters like time can be inferred from "tomorrow at 7am")

### OUTPUT SCHEMA (Strict JSON Only)
Output ONLY valid JSON with this structure. NO BACKSLASHES IN STRINGS:
{
    "is_complete": boolean,
    "response_text": "Brief answer/confirmation/single clarification question",
    "original_task": "Exact user input with backslashes converted to forward slashes (null if is_complete is false)",
    "personal_info": "One-sentence summary of personal info revealed (name, age, location, hobby, preference, etc.), or null if none"
}

### PATH FORMATTING RULE
Always convert Windows backslashes to forward slashes in original_task:
- Input: "C:\\Users\\file.txt" → Output: "C:/Users/file.txt"

### EXAMPLES

**Example 1: Question - Answer it**
Input: "What is a calculator?"
Output: {"is_complete": false, "response_text": "A calculator is a tool for performing mathematical calculations. Would you like me to open it?", "original_task": null, "personal_info": null}

**Example 2: Task with explicit target - Complete**
Input: "Open calculator"
Output: {"is_complete": true, "response_text": "Opening calculator.", "original_task": "Open calculator", "personal_info": null}

**Example 3: Task with filepath - Complete**
Input: "summarize the content of the file C:\\Users\\uscs\\Downloads\\coordinator to do.txt"
Output: {"is_complete": true, "response_text": "I'll summarize that file for you.", "original_task": "summarize the content of the file C:/Users/uscs/Downloads/coordinator to do.txt", "personal_info": null}

**Example 4: Task with time context - Complete**
Input: "set an alarm for 7 am tomorrow"
Output: {"is_complete": true, "response_text": "Setting alarm for 7 AM tomorrow.", "original_task": "set an alarm for 7 am tomorrow", "personal_info": null}

**Example 5: Vague task blocking execution - Incomplete**
Input: "send the message"
Output: {"is_complete": false, "response_text": "Who should I send the message to?", "original_task": null, "personal_info": null}

**Example 6: Task with inferrable defaults - Complete**
Input: "search for AI news"
Output: {"is_complete": true, "response_text": "Searching for AI news.", "original_task": "search for AI news", "personal_info": null}

**Example 7: Personal info detected**
Input: "My name is Jana and I'm a computer science student"
Output: {"is_complete": false, "response_text": "Nice to meet you, Jana! How can I help you today?", "original_task": null, "personal_info": "User's name is Jana and she is a computer science student"}

### TASK TO CLASSIFY:"""

# -----------------------
# Agent - CONVERSATIONAL CLARITY ONLY
# -----------------------
class LanguageAgent:
    def __init__(self, session_id: str = "default_session", user_id: str = "default_user"):
        """Initialize agent with session tracking and persistent storage"""
        print(f"🆕 Initializing agent for session: {session_id}, user: {user_id}")
        
        self.session_id = session_id
        self.user_id = user_id
        self.save_path = CONV_SAVE_PATH
        self.tasks_path = TASKS_SAVE_PATH
        self.system_prompt = {"role": "system", "content": SYSTEM_PROMPT}
        
        # Initialize MongoDB client for persistent storage
        try:
            from pymongo import MongoClient
            mongo_uri = os.getenv("MONGODB_URI")
            
            if not mongo_uri:
                logger.error("❌ MONGODB_URI not found in environment variables!")
                raise ValueError("MONGODB_URI not configured")
            
            self.mongo_client = MongoClient(mongo_uri)
            self.mongo_client.admin.command('ping')
            
            self.db = self.mongo_client["yusr_db"]
            self.conversations = self.db["language_agent_conversations"]
            
            logger.info(f"✅ Connected to MongoDB for session persistence")
        except Exception as e:
            logger.error(f"❌ Failed to connect to MongoDB: {e}")
            logger.warning("⚠️ Falling back to in-memory storage (will lose data on restart)")
            self.mongo_client = None
            self.conversations = None
        
        self.memory = self._load_conversation()
        
        logger.info(f"✅ Language Agent initialized for session {session_id}, user {user_id}")
        logger.info(f"📚 Loaded {len(self.memory) - 1} previous messages")
    
    def _load_conversation(self) -> List[Dict[str, str]]:
        """Load conversation history from MongoDB"""
        if self.conversations is None:
            logger.warning("⚠️ MongoDB not available, starting fresh conversation")
            return [self.system_prompt]
        
        try:
            doc = self.conversations.find_one(
                {"session_id": self.session_id, "user_id": self.user_id},
                sort=[("timestamp", -1)]
            )
            
            if doc and "messages" in doc:
                messages = doc["messages"]
                logger.info(f"✅ Loaded {len(messages)} messages from session {self.session_id}")
                
                if not messages or messages[0].get("role") != "system":
                    messages.insert(0, self.system_prompt)
                
                return messages
            else:
                logger.info(f"ℹ️ No previous conversation found for session {self.session_id}")
                return [self.system_prompt]
        except Exception as e:
            logger.error(f"❌ Failed to load conversation: {e}")
            return [self.system_prompt]
    
    def _save_conversation(self):
        """Save conversation to MongoDB"""
        if self.conversations is None:
            logger.debug("⚠️ MongoDB not available, skipping save")
            return
        
        try:
            import time
            self.conversations.update_one(
                {"session_id": self.session_id, "user_id": self.user_id},
                {
                    "$set": {
                        "messages": self.memory,
                        "timestamp": time.time(),
                        "last_updated": int(time.time())
                    }
                },
                upsert=True
            )
            logger.debug(f"💾 Saved conversation to MongoDB (session: {self.session_id})")
        except Exception as e:
            logger.error(f"❌ Failed to save conversation: {e}")

    def save_memory(self):
        """Save to both JSONL (backup) and MongoDB (persistence)"""
        try:
            append_jsonl(self.save_path, {
                "id": uuid.uuid4().hex,
                "timestamp": int(time.time()),
                "memory": self.memory,
                "session_id": self.session_id,
                "user_id": self.user_id
            })
        except Exception as e:
            logger.warning(f"⚠️ Failed to save to JSONL: {e}")
        
        self._save_conversation()

    def parse_response(self, response: str) -> tuple:
        """Parse LLM response to extract is_complete status and personal_info"""
        try:
            # FIX: Replace backslashes with forward slashes before parsing
            cleaned_response = response.replace("\\\\", "/").replace("\\", "/")
            parsed = json.loads(cleaned_response)
            is_complete = parsed.get("is_complete", False)
            response_text = parsed.get("response_text", "")
            personal_info = parsed.get("personal_info", None)
            # Normalize "null" string to None
            if personal_info and str(personal_info).lower() == "null":
                personal_info = None
            return response_text, is_complete, personal_info
        except json.JSONDecodeError as e:
            logger.error(f"⚠️ JSON parse error: {e}")
            logger.error(f"⚠️ Raw response: {response}")
            # Fallback: try to extract response_text manually
            try:
                import re
                match = re.search(r'"response_text":\s*"([^"]+)"', response)
                if match:
                    return match.group(1), False, None
            except:
                pass
            return "I'm sorry, I didn't quite understand. Could you clarify?", False, None
        except Exception as e:
            logger.warning(f"⚠️ Failed to parse response: {e}")
            return "I'm sorry, I didn't quite understand. Could you clarify?", False, None

    def user_turn(self, user_text: str) -> tuple:
        """Process user input and return response"""
        user_text = sanitize_text(user_text)
        self.memory.append({"role": "user", "content": user_text})
        
        # if len(self.memory) > 21:
        #     self.memory = [self.memory[0]] + self.memory[-20:]

        if len(self.memory) > 21:
                    # Preserve: system prompt + any injected "Previous Context" message
                    preserved = [self.memory[0]]
                    for msg in self.memory[1:]:
                        if msg.get("role") == "system" and "Previous Context" in msg.get("content", ""):
                            preserved.append(msg)
                            break  # only one context message ever exists
                    preserved.extend(self.memory[-20:])
                    self.memory = preserved
        
        print("   🤔 Thinking...", end=" ", flush=True)
        response = call_groq_api(self.memory, max_tokens=200)
        print("✓")
        
        if not response:
            response_text = "I'm having trouble connecting right now. Please try again."
            return response_text, False, None
        
        response_text, is_complete, personal_info = self.parse_response(response)

        self.memory.append({"role": "assistant", "content": response})
        self.save_memory()
        
        return response_text, is_complete, personal_info
    
    def clear_conversation(self):
        """Clear conversation history (for new chat)"""
        self.memory = [self.system_prompt]
        self._save_conversation()
        logger.info(f"🔄 Cleared conversation for session {self.session_id}")

# Store active agents by session_id
active_agents: Dict[str, LanguageAgent] = {}

async def start_language_agent(broker):
    print("="*70)
    print("🤖 CONVERSATIONAL CLARITY AGENT - READY (GROQ)!")
    print("="*70)
    print("Waiting for user requests...\n")
    
    def get_or_create_agent(session_id: str, user_id: str) -> LanguageAgent:
        """Get existing agent for session or create new one"""
        agent_key = f"{user_id}_{session_id}"
        
        if agent_key not in active_agents:
            logger.info(f"🆕 Creating new agent for session {session_id}, user {user_id}")
            active_agents[agent_key] = LanguageAgent(session_id, user_id)
        else:
            logger.info(f"♻️ Reusing existing agent for session {session_id}")
        
        return active_agents[agent_key]
    
    async def handle_user_input(message: dict):
        """Handle user input from HTTP API"""
        payload_data = message.payload if hasattr(message, 'payload') else message.get('payload', {})
        input_text = payload_data.get("input", "")
        device_type = payload_data.get("device_type", "desktop")
        
        print(f"📝 User said: {input_text}")
        print(f"📱 Device type: {device_type}")

        user_id = payload_data.get("user_id", "test_user")
        session_id = message.session_id if hasattr(message, 'session_id') else "default_session"
        http_request_id = message.message_id if hasattr(message, 'message_id') else str(uuid.uuid4())

        # NEW: Send thinking update
        try:
            await ThinkingStepManager.update_step(session_id, "Analyzing your request...", http_request_id)
        except Exception as e:
            logger.warning(f"⚠️ Failed to send thinking update: {e}")

        # Get or create agent for this session
        agent = get_or_create_agent(session_id, user_id)

        # Fetch Mem0 preferences
        try:
            # NEW: Send thinking update
            await ThinkingStepManager.update_step(session_id, "Checking your preferences...", http_request_id)
            
            from agents.coordinator_agent.memory.mem0_manager import get_preference_manager
            pref_mgr = get_preference_manager(user_id)
            
            all_memories = pref_mgr.get_relevant_preferences(input_text, limit=5)
            
            preferences = []
            conversation_history = []
            
            for memory in all_memories:
                # NEW CODE (USE THIS):
                # ✅ FIX: Add explicit None/empty check BEFORE iteration
                if not all_memories or all_memories is None:
                    logger.warning(f"⚠️ No memories found for user {user_id}")
                    all_memories = []

                # ✅ FIX: Ensure it's a list before iterating
                if not isinstance(all_memories, list):
                    logger.error(f"❌ get_relevant_preferences returned {type(all_memories)}, expected list")
                    all_memories = []

                if isinstance(memory, dict):
                    # metadata can exist but be None — handle that explicitly
                    metadata = memory.get('metadata')
                    if not isinstance(metadata, dict):
                        metadata = {}
                    category = metadata.get('category', 'general')
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
            
            context_parts = []
            
            if preferences:
                context_parts.append("# USER PREFERENCES")
                for i, pref in enumerate(preferences[:3], 1):
                    context_parts.append(f"{i}. {pref}")
            
            if conversation_history:
                context_parts.append("\n# RECENT CONVERSATIONS")
                for i, conv in enumerate(conversation_history[:2], 1):
                    context_parts.append(f"{i}. {conv}")
            
            memory_context = "\n".join(context_parts) if context_parts else "No previous context."
            
            print(f"🧠 Retrieved Memory Context:\n{memory_context}\n")
            #here
            # Always strip stale context first (even if new context is empty)
            agent.memory = [msg for msg in agent.memory if "Previous Context" not in msg.get("content", "")]

            if context_parts:
                memory_msg = {
                    "role": "system",
                    "content": f"Previous Context:\n{memory_context}"
                }
                if agent.memory and agent.memory[0].get("role") == "system":
                    agent.memory.insert(1, memory_msg)
                else:
                    agent.memory.insert(0, memory_msg)
                logger.info(f"✅ Injected {len(context_parts)} memory items into conversation")
            else:
                logger.info("ℹ️ No memory context available for this session")

        except Exception as e:
            logger.error(f"❌ Failed to fetch memory: {e}")

        # NEW: Send thinking update before calling agent
        await ThinkingStepManager.update_step(session_id, "Processing your request...", http_request_id)

        response, is_complete, personal_info = agent.user_turn(input_text)
        print(f"🤖 Agent: {response}\n")

        # Store personal info if extracted (no separate LLM call needed)
        if personal_info:
            try:
                from agents.coordinator_agent.memory.mem0_manager import get_preference_manager
                _pmgr = get_preference_manager(user_id)
                _pmgr.add_preference(
                    str(personal_info),
                    metadata={
                        "category": "personal_info",
                        "source": "language_agent",
                        "session_id": session_id
                    }
                )
                print(f"💾 Stored personal info: {personal_info}")
            except Exception as _ext_err:
                logger.warning(f"⚠️ Personal info storage (non-fatal): {_ext_err}")
        
        if is_complete:
            # NEW: Send thinking update
            await ThinkingStepManager.update_step(session_id, "Preparing for coordinator...", http_request_id)
            
            task_msg = AgentMessage(
                message_type=MessageType.TASK_REQUEST,
                sender=AgentType.LANGUAGE,
                receiver=AgentType.COORDINATOR,
                session_id=session_id,
                response_to=http_request_id,
                payload={
                    "confirmation": response, 
                    "device_type": device_type,
                    "user_id": user_id,
                }
            )
            await broker.publish(Channels.LANGUAGE_TO_COORDINATOR, task_msg)

        else:
            clarification_msg = AgentMessage(
                message_type=MessageType.CLARIFICATION_REQUEST,
                sender=AgentType.LANGUAGE,
                receiver=AgentType.LANGUAGE,
                session_id=session_id,
                response_to=http_request_id,
                payload={
                    "question": response,
                    "context": str(message),
                    "device_type": device_type
                }
            )
            await broker.publish(Channels.LANGUAGE_OUTPUT, clarification_msg)

    broker.subscribe(Channels.LANGUAGE_INPUT, handle_user_input)
    logger.info("✅ Language Agent started")

    while True:
        await asyncio.sleep(1)