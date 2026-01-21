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

Now classify this task:"""

# -----------------------
# Agent - CONVERSATIONAL CLARITY ONLY
# -----------------------
class TaskCoordinationAgent:
    def __init__(self):
        print("="*70)
        print("🤖 CONVERSATIONAL CLARITY AGENT - GROQ API")
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

    def parse_response(self, response: str) -> tuple:
        try:
            parsed = json.loads(response)
            is_complete = parsed.get("is_complete", False)
            response_text = parsed.get("response_text", "")
            return response_text, is_complete
        except Exception:
            # Safety fallback
            return "I'm sorry, I didn't quite understand. Could you clarify?", False

    def user_turn(self, user_text: str) -> tuple:
        user_text = sanitize_text(user_text)
        self.memory.append({"role": "user", "content": user_text})
        
        if len(self.memory) > 11:
            self.memory = [self.memory[0]] + self.memory[-10:]
        
        print("   🤔 Thinking...", end=" ", flush=True)
        response = call_groq_api(self.memory, max_tokens=200)
        print("✓")
        
        if not response:
            return "I'm having trouble connecting right now. Please try again.", False
        
        response_text, is_complete = self.parse_response(response)

        self.memory.append({"role": "assistant", "content": response})
        self.save_memory()
        
        return response_text, is_complete

##ADDED BY JANA BEGIN
async def start_language_agent(broker):
    agent = TaskCoordinationAgent()
    
    print("="*70)
    print("🤖 CONVERSATIONAL CLARITY AGENT - READY (GROQ)!")
    print("="*70)
    print("Waiting for user requests...\n")
    
    async def handle_user_input(message: dict):
        payload_data = message.payload if hasattr(message, 'payload') else message.get('payload', {})
        input_text = payload_data.get("input", "")
        
        print(f"📝 User said: {input_text}")

        user_id = payload_data.get("user_id", "default_user")
        session_id = message.session_id if hasattr(message, 'session_id') else "default_session"
        http_request_id = message.message_id if hasattr(message, 'message_id') else str(uuid.uuid4())

        # Memory / preferences block preserved exactly
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
            
            if context_parts:
                agent.memory.insert(1, {
                    "role": "system", 
                    "content": f"Previous Context:\n{memory_context}"
                })
        except Exception as e:
            logger.error(f"❌ Failed to fetch memory: {e}")

        response, is_complete = agent.user_turn(input_text)
        print(f"🤖 Agent: {response}\n")
        
        if is_complete:
            # Forward confirmation directly to coordinator
            task_msg = AgentMessage(
                message_type=MessageType.TASK_REQUEST,
                sender=AgentType.LANGUAGE,
                receiver=AgentType.COORDINATOR,
                response_to=http_request_id,
                payload={"confirmation": response}
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
