#!/usr/bin/env python3
"""
language_agent.py - GROQ API VERSION

CONVERSATIONAL CLARITY AGENT
- Sole role: gather missing information and confirm readiness
- NEVER decomposes tasks
- NEVER plans execution
- ONLY outputs structured JSON decisions
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
# SYSTEM PROMPT — NEW CLARITY AGENT ROLE (YOUR PROMPT)
# -----------------------
SYSTEM_PROMPT = """You are a **Conversational Clarity Agent**. Your sole job is to facilitate a human-like dialogue to ensure all necessary information for a task has been gathered.

**CONVERSATION RULES:**
1. **Analyze:** Review the **entire conversation history** (including the current user prompt) to determine if the task is complete and actionable.
2. **Goal:** Gather ALL necessary information (WHO, WHAT, WHERE, WHICH, etc.) for a clear task request.

**CRITICAL RESTRICTION:**
* **NEVER** decompose, analyze execution steps, or attempt to solve the task. Your only output is the structured JSON.

**OUTPUT FORMAT (MUST be valid JSON):**

For **INCOMPLETE** tasks (Need Clarification):
{
    "is_complete": false,
    "response_text": "A single, polite clarifying question based on missing information."
}

For **COMPLETE** tasks (Ready for Coordinator):
{
    "is_complete": true,
    "response_text": "A brief, polite confirmation that the details are gathered and the task will be passed on."
}

**CLARIFICATION GUIDE:**
* Ask only ONE specific question in "response_text".
* If the task is complete, the "response_text" must be a confirmation, NOT the original task text.

**EXAMPLES** (Self-Correction/Contextual):

Example 1 (VAGUE):
Input: "open the file"
Output: {"is_complete": false, "question": "Which file would you like to open? Please provide the filename and location."}

VAGUE (need clarification):
Input: "open the file"
Output: {"is_complete": false, "question": "Which file would you like to open? Please provide the filename and location."}

Input: "send a message"
Output: {"is_complete": false, "question": "To whom would you like to send a message? Which platform (Discord, WhatsApp, Email)?"}

Input: "download my assignment"
Output: {"is_complete": false, "question": "Which assignment do you need? Where is it located (Moodle, Google Drive, email)?"}

CLEAR (ready to process):
Input: "open calculator"
Output: {"is_complete": true, "task": "open calculator"}

Input: "search google for AI news"
Output: {"is_complete": true, "task": "search google for AI news"}

Input: "create a folder named Projects on desktop"
Output: {"is_complete": true, "task": "create a folder named Projects on desktop"}

Input: "open discord and send hello to server X"
Output: {"is_complete": true, "task": "open discord and send hello to server X"}

Input: "login to moodle and download assignment 3"
Output: {"is_complete": true, "task": "login to moodle and download assignment 3"}

Input: "open chrome and search for python tutorials"
Output: {"is_complete": true, "task": "open chrome and search for python tutorials"}

Input: "open calculator"
Output: {"is_complete": true, "task": "Got it. I have all the information and will pass this request on now."}

Now classify this task:"""

# -----------------------
# Agent - CONVERSATIONAL CLARITY ONLY
# -----------------------
# -----------------------
# Agent - CONVERSATIONAL CLARITY ONLY
# -----------------------
class TaskCoordinationAgent:
    def __init__(self, session_id: str = "default_session", user_id: str = "default_user"):
        """
        Initialize agent with session tracking and persistent storage
        
        Args:
            session_id: Unique session identifier
            user_id: User identifier for Mem0 preferences
        """
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
            # Test connection
            self.mongo_client.admin.command('ping')
            
            self.db = self.mongo_client["yusr_db"]
            self.conversations = self.db["language_agent_conversations"]
            
            logger.info(f"✅ Connected to MongoDB for session persistence")
        except Exception as e:
            logger.error(f"❌ Failed to connect to MongoDB: {e}")
            logger.warning("⚠️ Falling back to in-memory storage (will lose data on restart)")
            self.mongo_client = None
            self.conversations = None
        
        # Load existing conversation or create new
        self.memory = self._load_conversation()
        
        logger.info(f"✅ Language Agent initialized for session {session_id}, user {user_id}")
        logger.info(f"📚 Loaded {len(self.memory) - 1} previous messages")
    
    def _load_conversation(self) -> List[Dict[str, str]]:
        """Load conversation history from MongoDB"""
        if self.conversations is None:
            logger.warning("⚠️ MongoDB not available, starting fresh conversation")
            return [self.system_prompt]
        
        try:
            # Find the most recent conversation for this session
            doc = self.conversations.find_one(
                {"session_id": self.session_id, "user_id": self.user_id},
                sort=[("timestamp", -1)]
            )
            
            if doc and "messages" in doc:
                messages = doc["messages"]
                logger.info(f"✅ Loaded {len(messages)} messages from session {self.session_id}")
                
                # Ensure system prompt is first
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
        # Keep JSONL logging for debugging
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
        
        # Save to MongoDB for persistence
        self._save_conversation()

    def parse_response(self, response: str) -> tuple:
        """Parse LLM response to extract is_complete status"""
        try:
            parsed = json.loads(response)
            is_complete = parsed.get("is_complete", False)
            response_text = parsed.get("response_text", "")
            return response_text, is_complete
        except Exception as e:
            logger.warning(f"⚠️ Failed to parse JSON response: {e}")
            # Safety fallback
            return "I'm sorry, I didn't quite understand. Could you clarify?", False

    def user_turn(self, user_text: str) -> tuple:
        """Process user input and return response"""
        user_text = sanitize_text(user_text)
        self.memory.append({"role": "user", "content": user_text})
        
        # Trim memory to last 10 exchanges (keep system prompt)
        if len(self.memory) > 21:  # 1 system + 20 messages (10 exchanges)
            self.memory = [self.memory[0]] + self.memory[-20:]
        
        print("   🤔 Thinking...", end=" ", flush=True)
        response = call_groq_api(self.memory, max_tokens=200)
        print("✓")
        
        if not response:
            response_text = "I'm having trouble connecting right now. Please try again."
            return response_text, False
        
        response_text, is_complete = self.parse_response(response)

        self.memory.append({"role": "assistant", "content": response})
        self.save_memory()
        
        return response_text, is_complete
    
    def clear_conversation(self):
        """Clear conversation history (for new chat)"""
        self.memory = [self.system_prompt]
        self._save_conversation()
        logger.info(f"🔄 Cleared conversation for session {self.session_id}")

##ADDED BY JANA BEGIN
# async def start_language_agent(broker):
#     agent = TaskCoordinationAgent()
    
#     print("="*70)
#     print("🤖 CONVERSATIONAL CLARITY AGENT - READY (GROQ)!")
#     print("="*70)
#     print("Waiting for user requests...\n")
    
#     async def handle_user_input(message: dict):
#         payload_data = message.payload if hasattr(message, 'payload') else message.get('payload', {})
#         input_text = payload_data.get("input", "")
        
#         print(f"📝 User said: {input_text}")

#         user_id = payload_data.get("user_id", "default_user")
#         session_id = message.session_id if hasattr(message, 'session_id') else "default_session"
#         http_request_id = message.message_id if hasattr(message, 'message_id') else str(uuid.uuid4())

#         # Memory / preferences block preserved exactly
#         try:
#             from agents.coordinator_agent.memory.mem0_manager import get_preference_manager
#             pref_mgr = get_preference_manager(user_id)
            
#             all_memories = pref_mgr.get_relevant_preferences(input_text, limit=10)
            
#             preferences = []
#             conversation_history = []
            
#             for memory in all_memories:
#                 if isinstance(memory, dict):
#                     category = memory.get('metadata', {}).get('category', 'general')
#                     memory_text = memory.get('memory') or memory.get('text') or str(memory)
#                 elif isinstance(memory, str):
#                     memory_text = memory
#                     category = 'general'
#                 else:
#                     continue
                
#                 if 'conversation_history' in str(category):
#                     conversation_history.append(memory_text)
#                 else:
#                     preferences.append(memory_text)
            
#             context_parts = []
            
#             if preferences:
#                 context_parts.append("# USER PREFERENCES")
#                 for i, pref in enumerate(preferences[:5], 1):
#                     context_parts.append(f"{i}. {pref}")
            
#             if conversation_history:
#                 context_parts.append("\n# RECENT CONVERSATIONS")
#                 for i, conv in enumerate(conversation_history[:3], 1):
#                     context_parts.append(f"{i}. {conv}")
            
#             memory_context = "\n".join(context_parts) if context_parts else "No previous context."
            
#             print(f"🧠 Retrieved Memory Context:\n{memory_context}\n")
            
#             if context_parts:
#                 agent.memory.insert(1, {
#                     "role": "system", 
#                     "content": f"Previous Context:\n{memory_context}"
#                 })
#         except Exception as e:
#             logger.error(f"❌ Failed to fetch memory: {e}")

#         response, is_complete = agent.user_turn(input_text)
#         print(f"🤖 Agent: {response}\n")
        
#         if is_complete:
#             # Forward confirmation directly to coordinator
#             task_msg = AgentMessage(
#                 message_type=MessageType.TASK_REQUEST,
#                 sender=AgentType.LANGUAGE,
#                 receiver=AgentType.COORDINATOR,
#                 response_to=http_request_id,
#                 payload={"confirmation": response}
#             )
#             await broker.publish(Channels.LANGUAGE_TO_COORDINATOR, task_msg)

#         else:
#             clarification_msg = AgentMessage(
#                 message_type=MessageType.CLARIFICATION_REQUEST,
#                 sender=AgentType.LANGUAGE,
#                 receiver=AgentType.LANGUAGE,
#                 session_id=session_id,
#                 response_to=http_request_id,
#                 payload={
#                     "question": response,
#                     "context": str(message)
#                 }
#             )
#             await broker.publish(Channels.LANGUAGE_OUTPUT, clarification_msg)
        
#         if input_text.lower() in ["new chat", "start new chat", "reset conversation", "clear context"]:
#             session_control_msg = AgentMessage(
#                 message_type=MessageType.SESSION_CONTROL,
#                 sender=AgentType.LANGUAGE,
#                 receiver=AgentType.COORDINATOR,
#                 session_id=session_id,
#                 payload={"command": "start_new_chat"}
#             )
#             await broker.publish(Channels.SESSION_CONTROL, session_control_msg)
#             agent.memory = [{"role": "system", "content": SYSTEM_PROMPT}]
#             print("Conversation reset.\n")
#             return 
        
#         if input_text.lower().startswith("remember that"):
#             preference_text = input_text.replace("remember that", "").strip()
#             pref_msg = AgentMessage(
#                 message_type=MessageType.STORE_PREFERENCE,
#                 sender=AgentType.LANGUAGE,
#                 receiver=AgentType.COORDINATOR,
#                 session_id=session_id,
#                 payload={"preference": preference_text, "category": "explicit"}
#             )
#             await broker.publish(Channels.LANGUAGE_TO_COORDINATOR, pref_msg)

#     broker.subscribe(Channels.LANGUAGE_INPUT, handle_user_input)
#     logger.info("✅ Language Agent started")

#     while True:
#         await asyncio.sleep(1)
##ADDED BY JANA END
# Store active agents by session_id
active_agents: Dict[str, TaskCoordinationAgent] = {}

# Store active agents by session_id
active_agents: Dict[str, TaskCoordinationAgent] = {}

async def start_language_agent(broker):
    print("="*70)
    print("🤖 CONVERSATIONAL CLARITY AGENT - READY (GROQ)!")
    print("="*70)
    print("Waiting for user requests...\n")
    
    def get_or_create_agent(session_id: str, user_id: str) -> TaskCoordinationAgent:
        """Get existing agent for session or create new one"""
        agent_key = f"{user_id}_{session_id}"
        
        if agent_key not in active_agents:
            logger.info(f"🆕 Creating new agent for session {session_id}, user {user_id}")
            active_agents[agent_key] = TaskCoordinationAgent(session_id, user_id)
        else:
            logger.info(f"♻️ Reusing existing agent for session {session_id}")
        
        return active_agents[agent_key]
    
    async def handle_user_input(message: dict):
        payload_data = message.payload if hasattr(message, 'payload') else message.get('payload', {})
        input_text = payload_data.get("input", "")
        
        print(f"📝 User said: {input_text}")

        user_id = payload_data.get("user_id", "default_user")
        session_id = message.session_id if hasattr(message, 'session_id') else "default_session"
        http_request_id = message.message_id if hasattr(message, 'message_id') else str(uuid.uuid4())

        # Get or create agent for this session
        agent = get_or_create_agent(session_id, user_id)

        # Fetch Mem0 preferences
        try:
            from agents.coordinator_agent.memory.mem0_manager import get_preference_manager
            pref_mgr = get_preference_manager(user_id)
            
            all_memories = pref_mgr.get_relevant_preferences(input_text, limit=10)
            
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
            
            # Inject preferences ONLY if they exist and not already in memory
            if context_parts:
                # Check if preferences already injected
                has_preferences = any(
                    msg.get("role") == "system" and "Previous Context" in msg.get("content", "")
                    for msg in agent.memory
                )
                
                if not has_preferences:
                    agent.memory.insert(1, {
                        "role": "system", 
                        "content": f"Previous Context:\n{memory_context}"
                    })
                    logger.info("✅ Injected Mem0 context into conversation")
        except Exception as e:
            logger.error(f"❌ Failed to fetch memory: {e}")

        response, is_complete = agent.user_turn(input_text)
        print(f"🤖 Agent: {response}\n")
        
        if is_complete:
            # Extract full task context from conversation
            conversation_text = "\n".join([
                f"{m['role']}: {m['content']}" 
                for m in agent.memory if m['role'] in ['user', 'assistant']
            ])
            
            task_msg = AgentMessage(
                message_type=MessageType.TASK_REQUEST,
                sender=AgentType.LANGUAGE,
                receiver=AgentType.COORDINATOR,
                response_to=http_request_id,
                payload={
                    "action": input_text,
                    "context": "local",
                    "user_id": user_id,
                    "conversation_history": conversation_text
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
                    "context": str(message)
                }
            )
            await broker.publish(Channels.LANGUAGE_OUTPUT, clarification_msg)
        
        # Handle "new chat" command
        if input_text.lower() in ["new chat", "start new chat", "reset conversation", "clear context"]:
            session_control_msg = AgentMessage(
                message_type=MessageType.SESSION_CONTROL,
                sender=AgentType.LANGUAGE,
                receiver=AgentType.COORDINATOR,
                session_id=session_id,
                payload={"command": "start_new_chat"}
            )
            await broker.publish(Channels.SESSION_CONTROL, session_control_msg)
            
            # Clear agent conversation
            agent.clear_conversation()
            
            # Remove from active agents to force fresh load on next message
            agent_key = f"{user_id}_{session_id}"
            if agent_key in active_agents:
                del active_agents[agent_key]
            
            print("🔄 Conversation reset.\n")
            return 
        
        # Handle "remember that" command
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