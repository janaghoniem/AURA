import asyncio
import logging
import os
import base64
import tempfile
import time
import io
import wave
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from groq import Groq

# Import broker and agents
from agents.utils.broker import broker
from agents.language_agent import start_language_agent
from agents.coordinator_agent.coordinator_agent import start_coordinator_agent
from agents.reasoning_agent import start_reasoning_agent
# from agents.execution_agent.Coordinator import start_execution_agent
from agents.execution_agent.RAG.code_execution import initialize_execution_agent_for_server
from agents.utils.protocol import (
    AgentMessage, MessageType, AgentType, Channels,
    ClarificationMessage
)
from ThinkingStepManager import ThinkingStepManager
from routes.device_routes import router as device_router
from dotenv import load_dotenv
import json
from memory_api import router as memory_router

load_dotenv()

# Debug: Check which .env file was loaded and what keys are set
logger_debug = logging.getLogger("server_init")
groq_key = os.getenv("GROQ_API_KEY")
if groq_key:
    logger_debug.info(f"🔑 GROQ_API_KEY loaded: {groq_key[:20]}...{groq_key[-10:]}")
else:
    logger_debug.error("❌ GROQ_API_KEY NOT found in environment!")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Store pending responses (for HTTP API)
pending_responses = {}

# Store chat metadata (minimal tracking for sidebar)
# Format: {user_id: {session_id: {"title": str, "timestamp": int}}}
chat_metadata = {}

# Initialize Groq Client for TTS and STT
# PUT YOUR GROQ API KEY IN YOUR .env FILE AS: GROQ_API_KEY=your_key_here
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
if not GROQ_API_KEY:
    logger.warning("⚠️ GROQ_API_KEY not set - speech services will not work")
    groq_client = None
else:
    groq_client = Groq(api_key=GROQ_API_KEY)
    logger.info("✅ Groq client initialized for TTS and STT")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown"""
    # Startup
    logger.info("🚀 Starting AURA Backend...")
    
    # Start broker
    await broker.start()
    logger.info("✅ Broker started")
    
    # Subscribe to output channels BEFORE starting agents
    broker.subscribe(Channels.LANGUAGE_OUTPUT, handle_language_output)
    broker.subscribe(Channels.COORDINATOR_TO_LANGUAGE, handle_coordinator_output)
    logger.info("✅ Subscribed to output channels")
    
    # Start all agents as background tasks (don't wait for them)
    try:
        logger.info("🚀 Starting Language Agent...")
        asyncio.create_task(start_language_agent(broker))
        await asyncio.sleep(0.1)  # Allow task to register
        
        logger.info("🚀 Starting Coordinator Agent...")
        asyncio.create_task(start_coordinator_agent(broker))
        await asyncio.sleep(0.1)
        
        logger.info("🚀 Starting Reasoning Agent...")
        asyncio.create_task(start_reasoning_agent())
        await asyncio.sleep(0.1)
        
        logger.info("🚀 Starting Execution Agent...")
        asyncio.create_task(initialize_execution_agent_for_server(broker))
        await asyncio.sleep(0.1)
        
        logger.info("✅ All agents scheduled successfully")
    except Exception as e:
        logger.error(f"❌ Error starting agents: {e}", exc_info=True)
    
    # Yield control back to FastAPI so server can start
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down AURA Backend...")
    await broker.stop()
    logger.info("✅ Broker stopped")


app = FastAPI(
    title="YUSR Unified Backend (Pub/Sub)",
    description="Multi-agent system with message broker",
    version="3.0.0",
    lifespan=lifespan
)

# Include device routes
app.include_router(device_router)
app.include_router(memory_router)
logger.info("✅ Memory API routes registered at /api/memory")

# CORS for Electron
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React default
        "http://localhost:5173",  # Vite default
        "http://localhost:8080",  # Alternative
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger.info("✅ CORS middleware configured")


# ============================================================================
# HTTP API Endpoints
# ============================================================================

import re

def detect_language(text: str) -> str:
    """
    Detect if text is primarily Arabic or English
    Returns: 'arabic', 'english', or 'mixed'
    """
    # Count Arabic characters
    arabic_chars = len(re.findall(r'[\u0600-\u06FF]', text))
    # Count English letters
    english_chars = len(re.findall(r'[a-zA-Z]', text))
    
    total_chars = arabic_chars + english_chars
    if total_chars == 0:
        return 'english'  # Default to English for numbers/symbols only
    
    arabic_ratio = arabic_chars / total_chars
    
    if arabic_ratio > 0.7:
        return 'arabic'
    elif arabic_ratio < 0.3:
        return 'english'
    else:
        return 'mixed'


@app.post("/text-to-speech")
async def text_to_speech(request: Request):
    """
    Convert text to speech using Groq TTS with intelligent language detection
    FIX: Updated model name and voice mapping
    """
    try:
        logger.info("🔊 Received TTS request")
        
        if not groq_client:
            logger.error("❌ Groq client not initialized")
            raise HTTPException(status_code=500, detail="TTS service not available - GROQ_API_KEY not set")
        
        data = await request.json()
        text = data.get("text", "").strip()
        voice_name = data.get("voice_name")
        force_voice = data.get("force_voice", False)
        
        if not text:
            logger.error("❌ No text provided for TTS")
            raise HTTPException(status_code=400, detail="Missing 'text' field")
        
        # Auto-detect language if voice not specified or not forcing
        if not voice_name or not force_voice:
            detected_lang = detect_language(text)
            logger.info(f"🔍 Detected language: {detected_lang}")
            
            if not force_voice:
                if detected_lang == 'arabic':
                    voice_name = 'orpheus-arabic'
                    logger.info("🎤 Auto-selected Arabic voice")
                elif detected_lang == 'mixed':
                    arabic_chars = len(re.findall(r'[\u0600-\u06FF]', text))
                    total_alpha = len(re.findall(r'[\u0600-\u06FFa-zA-Z]', text))
                    if total_alpha > 0 and arabic_chars / total_alpha > 0.3:
                        voice_name = 'orpheus-arabic'
                        logger.info("🎤 Auto-selected Arabic voice for mixed text")
                    else:
                        voice_name = 'orpheus-english'
                        logger.info("🎤 Auto-selected English voice for mixed text")
                else:
                    voice_name = 'orpheus-english'
                    logger.info("🎤 Auto-selected English voice")
        
        if not voice_name:
            voice_name = 'orpheus-english'
        
        # FIX: Updated voice mapping with correct model names
        voice_mapping = {
            "orpheus-english": "canopylabs/orpheus-tts-v1-english",
            "orpheus-arabic": "canopylabs/orpheus-tts-v1-arabic-saudi",
            "arabic": "canopylabs/orpheus-tts-v1-arabic-saudi",
            "english": "canopylabs/orpheus-tts-v1-english",
            "Gacrux": "canopylabs/orpheus-tts-v1-english"  # Legacy fallback
        }
        
        groq_model = voice_mapping.get(voice_name, "canopylabs/orpheus-tts-v1-english")
        
        logger.info(f"🗣️ Generating speech for text: '{text[:50]}...'")
        logger.info(f"🎤 Using model: {groq_model}")
        
        # FIX: Generate TTS using correct model format
        response = groq_client.audio.speech.create(
            model=groq_model,  # Use full model name
            input=text
        )
        
        # Read the audio content
        audio_content = response.read()
        logger.info(f"✅ TTS generated: {len(audio_content)} bytes of audio data")
        
        # Convert to base64
        base64_audio = base64.b64encode(audio_content).decode('utf-8')
        logger.info(f"✅ Audio encoded: {len(base64_audio)} base64 characters")
        
        return {
            "status": "success",
            "audio_data": base64_audio,
            "format": "wav",
            "sample_rate": 24000,
            "voice_used": groq_model,
            "detected_language": detect_language(text)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ TTS error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"TTS failed: {str(e)}")

@app.post("/transcribe")
async def transcribe_audio(request: Request):
    """
    Transcribe audio using Groq Whisper API with multilingual support (Arabic + English)
    Automatically deletes audio after processing
    
    NOTE: This is STT (Speech-to-Text). For TTS (Text-to-Speech) in Arabic, 
    use the /text-to-speech endpoint with voice_name="orpheus-arabic"
    """
    try:
        logger.info("🎤 Received audio transcription request")

        if not groq_client:
            logger.error("❌ Groq client not initialized")
            raise HTTPException(status_code=500, detail="Transcription service not available")

        data = await request.json()
        audio_data = data.get("audio_data", "")
        session_id = data.get("session_id", "default")
        model = data.get("model", "whisper-large-v3")

        if not audio_data:
            raise HTTPException(status_code=400, detail="Missing 'audio_data'")

        # Decode base64 audio
        audio_bytes = base64.b64decode(audio_data)

        # Detect format extension
        file_extension = ".m4a" 
        if audio_bytes[:4] == b'RIFF': file_extension = ".wav"
        elif audio_bytes[:3] == b'ID3': file_extension = ".mp3"

        # Use tempfile to create a temporary file that we will delete manually
        with tempfile.NamedTemporaryFile(suffix=file_extension, delete=False) as temp_audio:
            temp_audio.write(audio_bytes)
            temp_path = temp_audio.name

        try:
            # Multilingual prompt for Arabic + English transcription
            # Whisper uses the prompt as context/guidance for transcription style
            bilingual_prompt = (
                "Transcribe exactly as spoken. "
                "Keep Arabic and English words mixed as-is. "
                "Do not translate between languages. "
                "افتح calculator, open التطبيق"
            )
            
            # Transcribe using Groq Whisper with multilingual support
            with open(temp_path, "rb") as audio_file:
                transcription = groq_client.audio.transcriptions.create(
                    file=(f"audio{file_extension}", audio_file),
                    model=model,
                    prompt=bilingual_prompt,  # Guide Whisper to preserve multilingual content
                    response_format="text",
                    language="ar",  # Set to Arabic to better detect mixed content
                    temperature=0.0 
                )

            transcript = transcription.strip()
            
            # Check for empty or silent audio
            if not transcript or len(transcript) < 2:
                logger.warning("⚠️ Empty or silent audio detected")
                transcript = "Couldn't catch that. Please try again."
            
            logger.info(f"📝 TRANSCRIBED TEXT: '{transcript}'")

            return {
                "status": "success",
                "transcript": transcript,
                "session_id": session_id
            }

        finally:
            # Ensure the file is deleted immediately after the API call
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                logger.info(f"🗑️ Deleted temporary file: {temp_path}")

    except Exception as e:
        logger.error(f"❌ Transcription error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")




@app.post("/session/new")
async def create_new_session(request: Request):
    """Create a new chat session and clear short-term memory"""
    try:
        data = await request.json()
        old_session_id = data.get("old_session_id")
        new_session_id = data.get("new_session_id")
        user_id = data.get("user_id", "test_user")
        
        logger.info(f"🔄 Creating new session: {old_session_id} → {new_session_id}")
        
        # Clear Language Agent's conversation history
        from agents.language_agent import active_agents
        agent_key = f"{user_id}_{old_session_id}"
        
        if agent_key in active_agents:
            logger.info(f"🗑️ Clearing conversation for {agent_key}")
            active_agents[agent_key].clear_conversation()
            # Remove old agent
            del active_agents[agent_key]
            logger.info(f"✅ Cleared and removed agent: {agent_key}")
        else:
            logger.info(f"ℹ️ No active agent found for {agent_key}")
        
        # Initialize metadata for new session
        if user_id not in chat_metadata:
            chat_metadata[user_id] = {}
        
        chat_metadata[user_id][new_session_id] = {
            "title": "New Chat",
            "timestamp": int(time.time())
        }
        
        # ✅ FIX: Send session control message to Coordinator to clear LangGraph checkpoint
        try:
            session_control_msg = AgentMessage(
                message_type=MessageType.STATUS_UPDATE,
                sender=AgentType.LANGUAGE,
                receiver=AgentType.COORDINATOR,
                session_id=old_session_id,
                payload={
                    "command": "start_new_chat",
                    "old_session_id": old_session_id,
                    "new_session_id": new_session_id
                }
            )
            
            # Publish to session control channel (Coordinator listens to this)
            await broker.publish(Channels.SESSION_CONTROL, session_control_msg)
            logger.info(f"✅ Sent session control message to Coordinator")
        except Exception as e:
            logger.warning(f"⚠️ Failed to send session control message: {e}")
        
        return {
            "status": "success",
            "old_session_id": old_session_id,
            "new_session_id": new_session_id,
            "message": "New chat session created. Short-term memory cleared."
        }
        
    except Exception as e:
        logger.error(f"❌ Session creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/process")
async def process_user_input(request: Request):
    """
    Main endpoint for user input
    
    Flow: HTTP → Language Agent → Coordinator → Execution → HTTP Response
    """
    try:
        data = await request.json()
        session_id = data.get("session_id", "default")
        user_input = data.get("input", "").strip()
        is_clarification = data.get("is_clarification", False)
        device_type = data.get("device_type", "mobile")
        user_id = data.get("user_id", "test_user")  # ✅ ADD THIS LINE
        
        if not user_input:
            raise HTTPException(status_code=400, detail="Missing 'input' field")
        
        logger.info(f"📥 HTTP request from session {session_id}: {user_input}")
        logger.info(f"📱 Device type: {device_type}")
        
        # Create message
        if is_clarification:
            message = AgentMessage(
                message_type=MessageType.CLARIFICATION_RESPONSE,
                sender=AgentType.LANGUAGE,
                receiver=AgentType.LANGUAGE,
                session_id=session_id,
                payload={"answer": user_input, "input": user_input, "device_type": device_type, "user_id": user_id}
            )
        else:
            message = AgentMessage(
                message_type=MessageType.TASK_REQUEST,
                sender=AgentType.LANGUAGE,
                receiver=AgentType.LANGUAGE,
                session_id=session_id,
                payload={"input": user_input, "device_type": device_type,"user_id": user_id}
            )
        
        logger.info(f"⏳ Creating pending response for message ID: {message.message_id}")
        future = asyncio.Future()
        pending_responses[message.message_id] = future
        logger.info(f"📝 Registered pending response. Total pending: {len(pending_responses)}")
        logger.info(f"📝 Pending IDs: {list(pending_responses.keys())}")
        
        # NEW: Send initial thinking update
        await ThinkingStepManager.update_step(session_id, "Processing input...", message.message_id)
        
        logger.info(f"📤 Publishing message to {Channels.LANGUAGE_INPUT}")
        await broker.publish(Channels.LANGUAGE_INPUT, message)
        
        logger.info(f"⏰ Waiting up to 60s for response...")
        try:
            response = await asyncio.wait_for(future, timeout=60.0)
            logger.info(f"✅ Response received: {response}")
            
            # NEW: Clear thinking steps
            await ThinkingStepManager.clear_steps(session_id)
            
            return response
        except asyncio.TimeoutError:
            logger.error(f"❌ TIMEOUT waiting for response to message: {message.message_id}")
            logger.error(f"❌ Pending responses at timeout: {list(pending_responses.keys())}")
            await ThinkingStepManager.clear_steps(session_id)
            raise HTTPException(status_code=504, detail="Request timeout")
        finally:
            if message.message_id in pending_responses:
                pending_responses.pop(message.message_id)
                logger.info(f"🗑️ Cleaned up pending response: {message.message_id}")
    
    except asyncio.TimeoutError:
        logger.error("❌ Request timeout - already handled in main flow")
        raise HTTPException(status_code=504, detail="Request timeout")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error processing request: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

"""
Fixed message handlers for server.py
Replace your handle_language_output and handle_coordinator_output functions with these
"""

async def handle_language_output(message):
    """Handle output from Language Agent - supports both dict and AgentMessage"""
    
    # Normalize to AgentMessage if it's a dict
    if isinstance(message, dict):
        logger.warning("⚠️ Received dict instead of AgentMessage from Language Agent, converting...")
        message = AgentMessage(**message)
    
    logger.info(f"📨 Received from Language Agent: {message.message_type}")
    logger.info(f"📋 Message ID: {message.message_id}")
    logger.info(f"📋 Response to: {message.response_to}")
    logger.info(f"📋 Payload: {message.payload}")
    logger.info(f"📋 Current pending responses: {list(pending_responses.keys())}")
    
    if message.message_type == MessageType.CLARIFICATION_REQUEST:
        response_content = {
            "status": "clarification_needed",
            "question": message.payload.get("question", "Need more information."),
            "response_id": message.message_id
        }
        
        logger.info(f"❓ Clarification needed: {response_content['question']}")
        
        target_id = message.response_to
        logger.info(f"🔍 Looking for pending response with ID: {target_id}")
        
        if target_id and target_id in pending_responses:
            logger.info(f"✅ FOUND! Resolving pending request: {target_id}")
            pending_responses[target_id].set_result(response_content)
            logger.info(f"✅ Response resolved successfully")
        else:
            logger.error(f"❌ NO PENDING RESPONSE FOUND for: {target_id}")
    
    elif message.message_type == MessageType.TASK_RESPONSE:
        response_content = {
            "status": "completed",
            "text": message.payload.get("response", "Task completed"),
            "task_id": message.task_id
        }
        
        logger.info(f"✅ Task response from Language Agent: {response_content}")
        
        target_id = message.response_to
        if target_id and target_id in pending_responses:
            logger.info(f"✅ Resolving pending request: {target_id}")
            pending_responses[target_id].set_result(response_content)
        else:
            logger.error(f"❌ NO PENDING RESPONSE FOUND for: {target_id}")


async def handle_coordinator_output(message):
    """Handle output from Coordinator - supports both dict and AgentMessage"""
    
    # Normalize to AgentMessage
    if isinstance(message, dict):
        logger.warning("⚠️ Received dict from Coordinator, converting...")
        try:
            message = AgentMessage(**message)
        except Exception as e:
            logger.error(f"❌ Failed to convert: {e}")
            logger.error(f"❌ Dict content: {message}")
            return
    
    logger.info(f"📨 Coordinator → Server: {message.message_type}")
    
    if message.message_type == MessageType.TASK_RESPONSE:
        result = message.payload
        
        # CHANGE 10A: Extract response text safely
        response_text = result.get("response")
        if not response_text:
            # Fallback to result details
            response_text = result.get("result", {}).get("details", "Task completed")
        
        # Extract chat title if present (from first message)
        chat_title = result.get("chat_title")
        
        # Update chat metadata if title is provided
        if chat_title:
            user_id = result.get("user_id", "test_user")
            session_id = message.session_id
            if user_id not in chat_metadata:
                chat_metadata[user_id] = {}
            if session_id in chat_metadata[user_id]:
                chat_metadata[user_id][session_id]["title"] = chat_title
                logger.info(f"✅ Updated chat title for {session_id}: '{chat_title}'")
        
        response = {
            "status": result.get("status", "completed"),
            "task_id": message.task_id,
            "text": response_text,  # This goes to TTS
            "result": result,
            "chat_title": chat_title  # Include title in response
        }
        
        logger.info(f"✅ Task completed, sending to TTS: '{response_text}'")
        
        target_id = message.response_to
        if target_id and target_id in pending_responses:
            logger.info(f"✅ Resolving pending request: {target_id}")
            pending_responses[target_id].set_result(response)
        else:
            logger.warning(f"⚠️ No pending response for {target_id}, trying fallback...")


@app.post("/reset")
async def reset_session(request: Request):
    """Reset a conversation session"""
    data = await request.json()
    session_id = data.get("session_id", "default")
    
    logger.info(f"🔄 Resetting session: {session_id}")
    
    # Broadcast reset message
    reset_msg = AgentMessage(
        message_type=MessageType.STATUS_UPDATE,
        sender=AgentType.LANGUAGE,
        receiver=AgentType.LANGUAGE,
        session_id=session_id,
        payload={"action": "reset"}
    )
    
    await broker.publish(Channels.BROADCAST, reset_msg)
    
    return {"status": "reset", "session_id": session_id}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "YUSR Unified Backend (Pub/Sub)",
        "version": "3.0.0",
        "broker": "running" if broker.running else "stopped",
        "transcription": "available (Groq Whisper)" if groq_client else "unavailable",
        "tts": "available (Groq Orpheus)" if groq_client else "unavailable"
    }


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "YUSR Unified Backend",
        "description": "Multi-agent system with message broker",
        "architecture": "Publisher/Subscriber",
        "version": "3.0.0",
        "endpoints": {
            "/process": "POST - Process user input",
            "/transcribe": "POST - Transcribe audio to text",
            "/text-to-speech": "POST - Convert text to speech",
            "/reset": "POST - Reset conversation session",
            "/health": "GET - Service health check"
        },
        "agents": {
            "language": "Natural language understanding",
            "coordinator": "Task orchestration",
            "execution": "UI automation"
        }
    }

from fastapi.responses import StreamingResponse

@app.get("/thinking-stream/{session_id}")
async def thinking_stream(session_id: str):
    """
    Server-Sent Events stream for thinking updates
    Frontend connects to this endpoint to receive real-time thinking steps
    """
    async def event_generator():
        thinking_queue = asyncio.Queue()
        
        async def handle_thinking_update(message):
            # Ensure we only process messages for THIS session
            msg_session = getattr(message, 'session_id', None)
            if msg_session == session_id:
                payload = getattr(message, 'payload', {})
                if isinstance(payload, dict):
                    await thinking_queue.put(payload)
        
        # Subscribe to broadcast channel
        broker.subscribe(Channels.BROADCAST, handle_thinking_update)
        logger.info(f"🔌 Client connected to thinking stream: {session_id}")
        
        try:
            while True:
                try:
                    # Wait for thinking updates with timeout
                    step = await asyncio.wait_for(thinking_queue.get(), timeout=30)
                    # Send JSON-formatted data so clients can parse safely
                    yield f"data: {json.dumps({ 'step': step })}\n\n"
                except asyncio.TimeoutError:
                    # Keep connection alive with heartbeat
                    yield ": heartbeat\n\n"
        except GeneratorExit:
            logger.info(f"🔌 Client disconnected from thinking stream: {session_id}")
        except Exception as e:
            logger.error(f"❌ Thinking stream error for {session_id}: {e}")
        finally:
            # Ensure we properly unsubscribe
            try:
                broker.unsubscribe(Channels.BROADCAST, handle_thinking_update)
                logger.info(f"🔌 Unsubscribed handler for session: {session_id}")
            except Exception as e:
                logger.warning(f"⚠️ Error during unsubscribe: {e}")
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/new-chat")
async def new_chat_endpoint(request: Request):
    """Handle new chat creation - clear session state and track new chat"""
    try:
        data = await request.json()
        session_id = data.get("session_id")
        user_id = data.get("user_id", "test_user")
        
        logger.info(f"🔄 New chat requested - clearing session: {session_id}")
        
        # Clear language agent conversation for this session
        from agents.language_agent import active_agents
        agent_key = f"{user_id}_{session_id}"
        
        if agent_key in active_agents:
            active_agents[agent_key].clear_conversation()
            logger.info(f"✅ Cleared language agent for {agent_key}")
        else:
            logger.info(f"ℹ️ No active agent found for {agent_key}")
        
        # Initialize new chat metadata (will be updated when first message completes)
        if user_id not in chat_metadata:
            chat_metadata[user_id] = {}
        
        chat_metadata[user_id][session_id] = {
            "title": "New Chat",
            "timestamp": int(time.time())
        }
        
        logger.info(f"📝 Initialized chat metadata for {session_id}")
        
        return {
            "status": "success", 
            "message": "New chat started",
            "session_id": session_id,
            "title": "New Chat"
        }
        
    except Exception as e:
        logger.error(f"❌ New chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/chats/{user_id}")
async def get_chats(user_id: str):
    """Get list of all chats for a user"""
    try:
        user_chats = chat_metadata.get(user_id, {})
        chats_list = [
            {
                "session_id": sid,
                "title": data.get("title", "Chat"),
                "timestamp": data.get("timestamp", 0)
            }
            for sid, data in user_chats.items()
        ]
        # Sort by timestamp descending (newest first)
        chats_list.sort(key=lambda x: x["timestamp"], reverse=True)
        
        logger.info(f"📋 Retrieved {len(chats_list)} chats for user {user_id}")
        return {"chats": chats_list}
        
    except Exception as e:
        logger.error(f"❌ Error getting chats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/update-chat-title")
async def update_chat_title(request: Request):
    """Update chat title (called when first message generates title)"""
    try:
        data = await request.json()
        session_id = data.get("session_id")
        user_id = data.get("user_id", "test_user")
        title = data.get("title", "Chat")
        
        if user_id not in chat_metadata:
            chat_metadata[user_id] = {}
        
        if session_id in chat_metadata[user_id]:
            chat_metadata[user_id][session_id]["title"] = title
            logger.info(f"✅ Updated chat title: {session_id} → '{title}'")
        
        return {"status": "success", "title": title}
        
    except Exception as e:
        logger.error(f"❌ Error updating chat title: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8000))
    logger.info(f"🚀 Starting server on 0.0.0.0:{port}")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )

