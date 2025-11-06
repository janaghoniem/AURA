#!/usr/bin/env python3
"""
smart_agent_gemini.py - GEMINI API VERSION

TASK COORDINATION AGENT — Gemini-2.0-Flash-Exp
- Full LLM-driven conversation (no hardcoded logic)
- LLM detects vagueness and when enough info is gathered
- LLM extracts all information and creates JSON
"""

import os, re, json, uuid, time, sys
from typing import List, Dict
import requests


##ADDED BY JANA BEGIN
import asyncio
import logging
from agents.utils.protocol import Channels
from agents.utils.broker import broker
from agents.utils.protocol import AgentMessage, MessageType, AgentType, ClarificationMessage

logger = logging.getLogger(__name__)
##ADDED BY JANA END

# -----------------------
# CONFIG - GEMINI API
# -----------------------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyCt__Y-bhQCVQZ7pdljv1KWXUoPryVVdHM")  # Set: export GEMINI_API_KEY=your_key
MODEL_NAME = "gemini-2.0-flash-exp"  # Smartest fast model
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent"

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
# Gemini API Call
# -----------------------
def call_gemini_api(messages: List[Dict[str, str]], max_tokens=MAX_TOKENS) -> str:
    """Call Google Gemini API"""
    
    if not GEMINI_API_KEY:
        raise ValueError("⚠️  GEMINI_API_KEY not set! Run: export GEMINI_API_KEY=your_key")
    
    # Convert messages to Gemini format
    # Gemini uses: system instruction + contents (user/model pairs)
    system_instruction = None
    contents = []
    
    for msg in messages:
        if msg['role'] == 'system':
            system_instruction = msg['content']
        elif msg['role'] == 'user':
            contents.append({
                "role": "user",
                "parts": [{"text": msg['content']}]
            })
        elif msg['role'] == 'assistant':
            contents.append({
                "role": "model",
                "parts": [{"text": msg['content']}]
            })
    
    # Build payload
    payload = {
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": 0.7,
            "topP": 0.9,
        }
    }
    
    # Add system instruction if present
    if system_instruction:
        payload["systemInstruction"] = {
            "parts": [{"text": system_instruction}]
        }
    
    try:
        response = requests.post(
            f"{API_URL}?key={GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        
        result = response.json()
        
        # Extract text from Gemini response
        if "candidates" in result and len(result["candidates"]) > 0:
            candidate = result["candidates"][0]
            if "content" in candidate and "parts" in candidate["content"]:
                text = candidate["content"]["parts"][0].get("text", "")
                return sanitize_text(text)
        
        return ""
            
    except requests.exceptions.RequestException as e:
        print(f"⚠️  API Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"    Response: {e.response.text}")
        return ""

# -----------------------
# System Prompts - LLM-DRIVEN
# -----------------------
SYSTEM_PROMPT = """You are a TASK COORDINATION AGENT. Your role is to gather information from users and prepare task instructions for execution agents that will carry out the actual work.

CRITICAL RULES:
1. You do NOT execute tasks yourself - you coordinate them
2. NEVER say "I can't do X" or "I don't have the ability to X"
3. ALWAYS respond as if the task WILL be done by downstream agents
4. DETECT VAGUENESS: If the user's request is unclear or missing critical details, ask specific clarifying questions
5. Ask clarifying questions to gather ALL necessary details (what, where, when, how, which file, etc.)
6. When you have COMPLETE information, respond with EXACTLY: "TASK_COMPLETE"
7. Only say "TASK_COMPLETE" when you have ALL details needed to execute the task

VAGUENESS DETECTION:
- "download my assignment" → VAGUE (which assignment? from where?)
- "help with homework" → VAGUE (what subject? what kind of help?)
- "open a website" → VAGUE (which website?)
- "download assignment1.pdf from Moodle MIU course to desktop/university" → CLEAR
- "search for AI news on Google" → CLEAR

Your responses should be:
- Helpful and confirming ("Sure, I can help coordinate that")
- Question-focused when vague (ask for specific missing details)
- Never refusing or explaining limitations
- Natural and conversational

Examples:

User: hi
You: Hello! How can I help you today?

User: can you help me
You: Of course! What do you need help with?

User: Download my assignment
You: I can help coordinate that download. Which assignment do you need, and where is it located (Moodle, Google Drive, email, etc.)?

User: I need help with my math homework
You: I can help with that. Where is the homework file, and what specific help do you need?

User: It's on Moodle in the Calculus course
You: Got it. What's the filename, and where would you like me to save it?

User: assignment1.pdf, save it to desktop/university folder
You: TASK_COMPLETE

User: Open Chrome and search for AI news
You: I can set that up. Should I search on a specific site like Google News, or just a general Google search?

User: Just Google search is fine
You: TASK_COMPLETE

User: Download the PDF from my email and summarize it
You: I can coordinate that. Which email contains the PDF (subject line or sender), and should I save it somewhere specific?

Remember: You are gathering information FOR execution agents. Always be helpful, detect vagueness, ask clarifying questions, and never refuse tasks. Only say TASK_COMPLETE when you have everything needed."""

DECOMPOSITION_PROMPT = """You are a task decomposition expert. Based on the conversation, create a detailed JSON task for the execution agent.

CONVERSATION HISTORY:
{conversation}

Your job:
1. Analyze the ENTIRE conversation
2. Extract ALL information provided
3. Create a JSON task in this EXACT format in the case of a single action:

{{
    "action": "describe_the_action",
    "context": "local (for Desktop applications, keyboard/mouse automation, UI interaction) / web (for Browser automation, web scraping, form filling)",
    "params": {{
        "action_type": open_app (requires additional parameters "app_name" OR "exe_path")/
                        click_element (requires additonal parameter "element")/
                        type_text (requires additional parameter "text")/
                        press_key (requires additional paramter "key")/
                        hotkey (requires additional paramter "keys[]")/
                        send_message (requires additional paramters "platform", "server_name", "message")/
                        navigate_window (requires additional paramters "window_title", "operation")/
                        file_operation (requires additional paramter "operation", "file_path")/
                        inspect (requires additional paramter "window_title"),
        "file_path": "use {{{{desktop_path}}}}, {{{{timestamp}}}} placeholders if mentioned",
        "content": "any content or placeholders like {{{{web_content}}}}",
        "file_type": "file extension if applicable"
    }},
    "task_id": "",
    "depends_on": "",
    "priority": "",
    "timeout": null,
    "retry_count": null
}}

4. Create a JSON task in this EXACT format in the case of multiple dependant actions (for example, open an app then perform a certain action like write or click):

[
    {{
    "task_id": "id of this task",
    "action": "describe_the_action",
    "context": "local / web",
    "params": {{
        "action_type": open_app (requires additional parameters "app_name" OR "exe_path")/
                        click_element (requires additonal parameter "element")/
                        type_text (requires additional parameter "text")/
                        press_key (requires additional paramter "key")/
                        hotkey (requires additional paramter "keys[]")/
                        send_message (requires additional paramters "platform", "server_name", "message")/
                        navigate_window (requires additional paramters "window_title", "operation")/
                        file_operation (requires additional paramter "operation", "file_path")/
                        inspect (requires additional paramter "window_title"),
        "file_path": "use {{{{desktop_path}}}}, {{{{timestamp}}}} placeholders if mentioned",
        "content": "any content or placeholders like {{{{web_content}}}}",
        "file_type": "file extension if applicable"
    }},
    "depends_on": "id of previous task if any"
    }},
    {{
    "task_id": "id of this task",
    "action": "describe_the_action",
    "context": "local / web",
    "params": {{
        "action_type": open_app (requires additional parameters "app_name" OR "exe_path")/
                        click_element (requires additonal parameter "element")/
                        type_text (requires additional parameter "text")/
                        press_key (requires additional paramter "key")/
                        hotkey (requires additional paramter "keys[]")/
                        send_message (requires additional paramters "platform", "server_name", "message")/
                        navigate_window (requires additional paramters "window_title", "operation")/
                        file_operation (requires additional paramter "operation", "file_path")/
                        inspect (requires additional paramter "window_title"),
        "file_path": "use {{{{desktop_path}}}}, {{{{timestamp}}}} placeholders if mentioned",
        "content": "any content or placeholders like {{{{web_content}}}}",
        "file_type": "file extension if applicable"
    }},
    "depends_on": "id of previous task if any"
    }}
]
        


IMPORTANT:
- Leave empty fields as empty strings ""
- Leave numeric fields as null if not specified
- Use placeholders like {{{{desktop_path}}}}, {{{{timestamp}}}}, {{{{web_content}}}} where appropriate
- The action can be ANYTHING the user described - don't limit to predefined actions
- Extract ALL details from the conversation into action_type
- Be comprehensive - include source, destination, file names, everything

Respond with ONLY the JSON, nothing else."""

# -----------------------
# Agent - FULL LLM DRIVEN
# -----------------------
class TaskCoordinationAgent:
    def __init__(self):
        print("="*70)
        print("🤖 TASK COORDINATION AGENT - GEMINI API")
        print("="*70)
        print(f"📡 Using: {MODEL_NAME}")
        print(f"🔑 API Key: {'✓ Set' if GEMINI_API_KEY else '✗ Missing'}")
        print("="*70 + "\n")
        
        if not GEMINI_API_KEY:
            print("⚠️  WARNING: GEMINI_API_KEY not found!")
            print("   Set it with: export GEMINI_API_KEY=your_key\n")
            print("   Get your key from: https://aistudio.google.com/app/apikey\n")
        
        self.memory = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.save_path = CONV_SAVE_PATH
        self.tasks_path = TASKS_SAVE_PATH

    def save_memory(self):
        """Save conversation to JSONL"""
        append_jsonl(self.save_path, {
            "id": uuid.uuid4().hex,
            "timestamp": int(time.time()),
            "memory": self.memory
        })

    def check_completion(self, response: str) -> bool:
        """Check if LLM signals task is complete"""
        return "TASK_COMPLETE" in response

    async def decompose_task(self):
        """Let LLM extract information and create JSON"""
        
        print("\n" + "="*70)
        print("🎯 TASK DECOMPOSITION")
        print("="*70 + "\n")
        
        # Build conversation history for LLM
        conversation = "\n".join([
            f"{m['role'].upper()}: {m['content']}" 
            for m in self.memory if m['role'] in ['user', 'assistant']
        ])
        
        # Ask LLM to create the JSON
        decomp_messages = [
            {"role": "system", "content": "You are a task decomposition expert that creates JSON tasks."},
            {"role": "user", "content": DECOMPOSITION_PROMPT.format(conversation=conversation)}
        ]
        
        print("📊 Asking LLM to analyze conversation and create JSON...")
        response = call_gemini_api(decomp_messages, max_tokens=500)
        
        # Try to extract JSON from response
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            try:
                task = json.loads(json_match.group())
            except json.JSONDecodeError:
                print("⚠️  LLM response was not valid JSON, using fallback structure\n")
                task = {
                    "action": "user_request",
                    "context": "system",
                    "strategy": "system",
                    "params": {
                        "action_type": conversation[:300],
                        "file_path": "",
                        "content": "",
                        "file_type": ""
                    },
                    "task_id": "",
                    "depends_on": "",
                    "priority": "",
                    "timeout": None,
                    "retry_count": None
                }
        else:
            print("⚠️  Could not find JSON in LLM response, using fallback\n")
            task = {
                "action": "user_request",
                "context": "system",
                "strategy": "system",
                "params": {
                    "action_type": conversation[:300],
                    "file_path": "",
                    "content": "",
                    "file_type": ""
                },
                "task_id": "",
                "depends_on": "",
                "priority": "",
                "timeout": None,
                "retry_count": None
            }

        ##COMMENTED BY JANA BEGIN
        
        # # Save to file
        # append_jsonl(self.tasks_path, {
        #     "timestamp": int(time.time()),
        #     "task": task
        # })
        
        # print("📋 Generated Task JSON:")
        # print(json.dumps(task, indent=2))
        # print(f"\n💾 Saved to: {self.tasks_path}")
        # print("="*70 + "\n")

        ##COMMENTED BY JANA END

        ##ADDED BY JANA BEGIN
        logger.info(f"📋 Generated Task JSON: {task} ")
        await broker.publish(Channels.LANGUAGE_TO_COORDINATOR, task)
        ##ADDED BY JANA END 

        # return task

    def user_turn(self, user_text: str) -> tuple:
        """Process user input, return (response, is_complete)"""
        
        user_text = sanitize_text(user_text)
        
        # Add user message to memory
        self.memory.append({"role": "user", "content": user_text})
        
        # Keep only recent history (system + last 10 messages)
        if len(self.memory) > 11:
            self.memory = [self.memory[0]] + self.memory[-10:]
        
        # Generate response from LLM
        print("   🤔 Thinking...", end=" ", flush=True)
        response = call_gemini_api(self.memory, max_tokens=200)
        print("✓")
        
        if not response:
            response = "I'm having trouble connecting. Please try again."
            return response, False
        
        # Check if task is complete
        is_complete = self.check_completion(response)
        
        # Clean up response for display (remove TASK_COMPLETE marker)
        display_response = response.replace("TASK_COMPLETE", "").strip()
        if not display_response and is_complete:
            display_response = "Perfect! I have all the information. Creating the task now..."
        
        # Add assistant response to memory
        self.memory.append({"role": "assistant", "content": response})
        
        # Save memory
        self.save_memory()
        
        return display_response, is_complete
    
##ADDED BY JANA BEGIN
# -----------------------
# Async Agent Starter for Broker
# -----------------------
async def start_language_agent(broker):
    agent = TaskCoordinationAgent()
    
    print("="*70)
    print("🤖 TASK COORDINATION AGENT - READY!")
    print("="*70)
    print("Waiting for user requests...\n")
    
    async def handle_user_input(message: dict):
        print(f"📝 User said: {message.payload}")

        # Process input with LLM
        response, is_complete = agent.user_turn(message.payload["input"])
        
        # Display response
        print(f"🤖 Agent: {response}\n")
        
        # Auto-decompose if complete
        if is_complete:
            print("✅ Task information complete!\n")
            await agent.decompose_task()
            
            # Reset for next task
            agent.memory = [{"role": "system", "content": SYSTEM_PROMPT}]
            print("🔄 Ready for next task!\n")
        else:
            clarification_msg = AgentMessage(
                message_type=MessageType.CLARIFICATION_REQUEST,
                sender=AgentType.LANGUAGE,
                receiver=AgentType.LANGUAGE, # Or LANGUAGE_OUTPUT, depends on your routing
                session_id=message.session_id,
                response_to=message.message_id,
                payload={
                    "question": response,
                    "context": message.model_dump()
                }
            )
            
            await broker.publish(Channels.LANGUAGE_OUTPUT, clarification_msg)

    broker.subscribe(Channels.LANGUAGE_INPUT, handle_user_input)
    logger.info("✅ Language Agent started")

    while True:
        await asyncio.sleep(1)
##ADDED BY JANA END