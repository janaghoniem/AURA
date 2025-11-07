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
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")  # Set: export GEMINI_API_KEY=your_key
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

Examples:

User: What is a calculator?
You: A calculator is an application for performing mathematical calculations. Would you like me to open it?

User: open calculator
You: TASK_COMPLETE

User: launch notepad
You: TASK_COMPLETE

User: start chrome
You: TASK_COMPLETE

User: open word
You: TASK_COMPLETE

User: search for AI news
You: TASK_COMPLETE

User: download my assignment
You: Which assignment file do you need, and where is it located?

User: open the document
You: Which document would you like to open?

User: open report.docx from downloads
You: TASK_COMPLETE

User: send a message
You: What message would you like to send, and to whom?

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

TASK DECOMPOSITION:
1. Identify ALL distinct actions in the user's request
2. Break down complex actions into granular steps (open app → wait → navigate → click → type → send)
3. Create separate task objects for each action
4. Set "depends_on" to link sequential tasks
5. Generate unique task_ids (task_001, task_002, etc.)

CONTEXT DETERMINATION:
- "local" → Desktop apps (Calculator, Notepad, Word, Excel, PowerPoint, File Explorer, Discord, WhatsApp, ANY desktop application), file operations, keyboard/mouse actions
- "web" → Browser operations (search, navigate, login, scrape, download from web)

CRITICAL: File operations (open file, save file, move file) = "local" context!

ACTION_TYPE RULES - USE THESE EXACT VALUES:

LOCAL context:
- "open_app" → For: calculator, notepad, chrome, word, excel, discord, any app name
- "wait_for_app" → For: waiting for app to load
- "hotkey" → For: keyboard shortcuts (Ctrl+K, Ctrl+C, etc.)
- "click_element" → For: clicking UI elements (buttons, channels, items)
- "type_text" → For: typing text in fields
- "press_key" → For: single key presses (Enter, Tab, Escape)
- "wait" → For: pausing between actions
- "send_message" → For: Discord, WhatsApp messages
- "join_voice_channel" → For: joining voice channels
- "leave_voice_channel" → For: leaving voice channels
- "file_operation" → For: opening files, saving files, moving files

WEB context:
- "navigate" → For: opening URLs, web searches
- "login" → For: logging into websites
- "download" → For: downloading from web
- "fill_form" → For: filling web forms
- "open_browser" → For: opening web browsers
- "close_browser" → For: closing web browsers
- "web_search" → For: performing web searches
- "extract_data" → For: extracting data from web pages


PARAMETER STRUCTURE:

Opening applications:
{{
    "action_type": "open_app",
    "app_name": "Discord"
}}

Wait for app to load:
{{
    "action_type": "wait_for_app",
    "app_name": "Discord",
    "wait_time": 5
}}

Hotkey/keyboard shortcut:
{{
    "action_type": "hotkey",
    "keys": ["ctrl", "k"]
}}

Type text:
{{
    "action_type": "type_text",
    "text": "search text here"
}}

Press single key:
{{
    "action_type": "press_key",
    "key": "enter"
}}

Click UI element:
{{
    "action_type": "click_element",
    "element": {{
        "text": "element name",
        "type": "button/channel/item"
    }}
}}

Wait/pause:
{{
    "action_type": "wait",
    "duration": 3
}}

Join voice channel:
{{
    "action_type": "join_voice_channel",
    "channel_name": "General Voice"
}}

Send message:
{{
    "action_type": "send_message",
    "platform": "discord",
    "server_name": "ServerName",
    "message": "message text"
}}

Save file:
{{
    "action_type": "save_file",
    "file_path": "path/to/file",
    "content": "file content"
}}

Web search:
{{
    "action_type": "navigate",
    "url": "https://www.bing.com/search?q=search+terms"
}}

Download from web:
{{
    "action_type": "download",
    "url": "download_url",
    "download_path": "{{downloads_path}}/filename"
}}

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

FIELD RULES:
- "task_id": Always empty string ""
- "depends_on": Empty string "" for all tasks
- "priority": Always empty string ""
- "timeout": Always null
- "retry_count": Always null

SINGLE TASK EXAMPLES:

"open calculator":
[
    {{
        "task_id": "",
        "action": "open_calculator",
        "context": "local",
        "params": {{
            "action_type": "open_app",
            "app_name": "Calculator"
        }},
        "depends_on": "",
        "priority": "",
        "timeout": null,
        "retry_count": null
    }}
]

"search for AI news":
[
    {{
        "task_id": "",
        "action": "search_ai_news",
        "context": "web",
        "params": {{
            "action_type": "navigate",
            "url": "https://www.bing.com/search?q=AI+news"
        }},
        "depends_on": "",
        "priority": "",
        "timeout": null,
        "retry_count": null
    }}
]

"search on apple on google chrome":
[
    {{
        "task_id": "",
        "action": "open_chrome",
        "context": "local",
        "params": {{
            "action_type": "open_app",
            "app_name": "Chrome"
        }},
        "depends_on": "",
        "priority": "",
        "timeout": null,
        "retry_count": null
    }},
    {{
        "task_id": "",
        "action": "search_apple",
        "context": "web",
        "params": {{
            "action_type": "navigate",
            "url": "https://www.bing.com/search?q=apple"
        }},
        "depends_on": "",
        "priority": "",
        "timeout": null,
        "retry_count": null
    }}
]

MULTI-TASK EXAMPLES:

"download my assignment from moodle then open it":
[
    {{
        "task_id": "",
        "action": "navigate_to_moodle",
        "context": "web",
        "params": {{
            "action_type": "navigate",
            "url": "https://moodle.university.edu"
        }},
        "depends_on": "",
        "priority": "",
        "timeout": "",
        "retry_count": ""
    }},
    {{
        "task_id": "",
        "action": "download_assignment",
        "context": "web",
        "params": {{
            "action_type": "download",
            "url": "moodle_assignment_url",
            "download_path": "{{downloads_path}}/assignment.pdf"
        }},
        "depends_on": "",
        "priority": "",
        "timeout": "",
        "retry_count": ""
    }},
    {{
        "task_id": "",
        "action": "wait_download_complete",
        "context": "local",
        "params": {{
            "action_type": "wait",
            "duration": 3
        }},
        "depends_on": "",
        "priority": "",
        "timeout": "",
        "retry_count": ""
    }},
    {{
        "task_id": "",
        "action": "open_assignment",
        "context": "local",
        "params": {{
            "action_type": "file_operation",
            "operation": "open",
            "file_path": "{{downloads_path}}/assignment.pdf",
            "file_type": "pdf"
        }},
        "depends_on": "",
        "priority": "",
        "timeout": "",
        "retry_count": ""
    }}
]

"open discord and send a message to habiba's server":
[
    {{
        "task_id": "",
        "action": "open_discord",
        "context": "local",
        "params": {{
            "action_type": "open_app",
            "app_name": "Discord"
        }},
        "depends_on": "",
        "priority": "",
        "timeout": "",
        "retry_count": ""
    }},
    {{
        "task_id": "",
        "action": "wait_discord_load",
        "context": "local",
        "params": {{
            "action_type": "wait_for_app",
            "app_name": "Discord",
            "wait_time": 5
        }},
        "depends_on": "",
        "priority": "",
        "timeout": "",
        "retry_count": ""
    }},
    {{
        "task_id": "",
        "action": "open_quick_switcher",
        "context": "local",
        "params": {{
            "action_type": "hotkey",
            "keys": ["ctrl", "k"]
        }},
        "depends_on": "",
        "priority": "",
        "timeout": "",
        "retry_count": ""
    }},
    {{
        "task_id": "",
        "action": "search_server",
        "context": "local",
        "params": {{
            "action_type": "type_text",
            "text": "habiba'server"
        }},
        "depends_on": "",
        "priority": "",
        "timeout": "",
        "retry_count": ""
    }},
    {{
        "task_id": "",
        "action": "select_server",
        "context": "local",
        "params": {{
            "action_type": "press_key",
            "key": "enter"
        }},
        "depends_on": "",
        "priority": "",
        "timeout": "",
        "retry_count": ""
    }},
    {{
        "task_id": "",
        "action": "wait_server_load",
        "context": "local",
        "params": {{
            "action_type": "wait",
            "duration": 3
        }},
        "depends_on": "",
        "priority": "",
        "timeout": "",
        "retry_count": ""
    }},
    {{
        "task_id": "",
        "action": "find_text_channel",
        "context": "local",
        "params": {{
            "action_type": "click_element",
            "element": {{
                "text": "general",
                "type": "text_channel"
            }}
        }},
        "depends_on": "",
        "priority": "",
        "timeout": "",
        "retry_count": ""
    }},
    {{
        "task_id": "",
        "action": "focus_message_box",
        "context": "local",
        "params": {{
            "action_type": "press_key",
            "key": "tab"
        }},
        "depends_on": "",
        "priority": "",
        "timeout": "",
        "retry_count": ""
    }},
    {{
        "task_id": "",
        "action": "send_message",
        "context": "local",
        "params": {{
            "action_type": "send_message",
            "platform": "discord",
            "server_name": "habiba'server",
            "message": "Hello from automation!"
        }},
        "depends_on": "",
        "priority": "",
        "timeout": "",
        "retry_count": ""
    }}
]

GRANULARITY RULES:
- Break complex actions into atomic steps
- Include waits after app launches and between major actions
- Include hotkeys/shortcuts when applicable
- Include element clicking for UI navigation
- Include key presses for confirmations

RULES:
- ALWAYS return a JSON array (even for single tasks)
- Use "local" for desktop apps and file operations
- Use "web" for browser operations
- Use exact action_type values listed above
- app_name is just the name (Calculator, Notepad, Chrome, Word, Discord)
- Extract file extensions to file_type
- ALL fields that should be empty: use empty string ""
- ALL numeric fields that are unused: use null
- "task_id": ALWAYS ""
- "depends_on": ALWAYS ""
- "priority": ALWAYS ""
- "timeout": ALWAYS null
- "retry_count": ALWAYS null

Output ONLY the JSON array. Do not include any explanatory text before or after the JSON."""

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