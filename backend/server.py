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
# Use Google Cloud Speech-to-Text and Text-to-Speech
from google.cloud import speech
from google.cloud import texttospeech

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
google_creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
if google_creds:
    logger_debug.info(f"🔑 GOOGLE_APPLICATION_CREDENTIALS loaded: {google_creds}")
else:
    logger_debug.warning("❌ GOOGLE_APPLICATION_CREDENTIALS NOT found in environment! Set path to service account JSON in this variable.")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Store pending responses (for HTTP API)
pending_responses = {}

# Initialize Google Cloud Speech and Text-to-Speech clients
GOOGLE_CREDS = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
if not GOOGLE_CREDS:
    logger.warning("⚠️ GOOGLE_APPLICATION_CREDENTIALS not set - Google Cloud speech services may not work")

try:
    speech_client = speech.SpeechClient()
    tts_client = texttospeech.TextToSpeechClient()
    logger.info("✅ Google Cloud Speech and TTS clients initialized")
except Exception as e:
    logger.error(f"❌ Failed to initialize Google Cloud clients: {e}")
    speech_client = None
    tts_client = None


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
    Convert text to speech using Google Cloud Text-to-Speech.
    Supports language auto-detection and voice/dialect selection via `voice_name` or `language`.
    Returns MP3 audio in base64.
    """
    try:
        logger.info("🔊 Received TTS request")

        if not tts_client:
            logger.error("❌ Google TTS client not initialized")
            raise HTTPException(status_code=500, detail="TTS service not available")

        data = await request.json()
        text = data.get("text", "").strip()
        voice_name = data.get("voice_name")
        force_voice = data.get("force_voice", False)
        requested_language = data.get("language")

        if not text:
            logger.error("❌ No text provided for TTS")
            raise HTTPException(status_code=400, detail="Missing 'text' field")

        detected_lang = detect_language(text)
        logger.info(f"🔍 Detected language: {detected_lang}")

        # Language/dialect resolution
        # If client provided explicit language/dialect, prefer it (example: 'ar-EG' or 'ar-SA')
        language_code = None
        if requested_language:
            # Normalize common short forms
            if requested_language.lower().startswith('ar'):
                # Map variants to Google-style codes
                language_code = requested_language if '-' in requested_language else f"{requested_language}-SA"
            elif requested_language.lower().startswith('en'):
                language_code = requested_language if '-' in requested_language else "en-US"
        else:
            language_map = {"arabic": "ar-SA", "english": "en-US", "mixed": "en-US"}
            language_code = language_map.get(detected_lang, "en-US")

        # Voice mapping - friendly names -> Google voices (common Wavenet)
        voice_mapping = {
            "Gacrux": "en-US-Wavenet-D",
            "default_en": "en-US-Wavenet-F",
            "default_ar": "ar-XA-Wavenet-A",
            "orpheus-english": "en-US-Wavenet-F",
            "orpheus-arabic": "ar-XA-Wavenet-A",
        }

        if not voice_name or not force_voice:
            if detected_lang == 'arabic':
                voice_name = 'orpheus-arabic'
            else:
                voice_name = voice_name or 'Gacrux'

        google_voice = voice_mapping.get(voice_name, voice_mapping['Gacrux'])

        synthesis_input = texttospeech.SynthesisInput(text=text)

        voice_params = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            name=google_voice,
            ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL,
        )

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )

        response = tts_client.synthesize_speech(
            input=synthesis_input,
            voice=voice_params,
            audio_config=audio_config,
        )

        audio_content = response.audio_content
        base64_audio = base64.b64encode(audio_content).decode('utf-8')

        return {
            "status": "success",
            "audio_data": base64_audio,
            "format": "mp3",
            "sample_rate": 24000,
            "voice_used": google_voice,
            "detected_language": detected_lang,
            "language_code": language_code,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ TTS error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"TTS failed: {str(e)}")

@app.post("/transcribe")
async def transcribe_audio(request: Request):
    """
    Transcribe audio using Google Cloud Speech-to-Text.
    Accepts base64-encoded audio bytes and optional `language` or `language_hints` to favor dialects.
    """
    try:
        logger.info("🎤 Received audio transcription request")

        if not speech_client:
            logger.error("❌ Google Speech client not initialized")
            raise HTTPException(status_code=500, detail="Transcription service not available")

        data = await request.json()
        audio_data = data.get("audio_data", "")
        session_id = data.get("session_id", "default")
        requested_language = data.get("language")  # e.g., 'ar-SA' or 'ar-EG' or 'en-US'
        language_hints = data.get("language_hints", [])  # list of languages to assist

        if not audio_data:
            raise HTTPException(status_code=400, detail="Missing 'audio_data'")

        audio_bytes = base64.b64decode(audio_data)

        # Try to detect common encodings
        if audio_bytes[:4] == b'RIFF':
            encoding = speech.RecognitionConfig.AudioEncoding.LINEAR16
        elif audio_bytes[:3] == b'ID3' or audio_bytes[:2] == b'\xff\xfb':
            encoding = speech.RecognitionConfig.AudioEncoding.MP3
        elif audio_bytes[:4] == b"\x1A\x45\xDF\xA3":
            encoding = speech.RecognitionConfig.AudioEncoding.WEBM_OPUS
        else:
            encoding = speech.RecognitionConfig.AudioEncoding.ENCODING_UNSPECIFIED

        # Determine language code: prefer explicit request, otherwise default to Arabic+English hints
        if requested_language:
            language_code = requested_language
        else:
            language_code = "en-US"

        # If no hints provided, offer both Arabic and English to allow mixed recognition
        if not language_hints:
            language_hints = ["ar-SA", "en-US"]

        config = speech.RecognitionConfig(
            encoding=encoding,
            sample_rate_hertz=16000,
            language_code=language_code,
            alternative_language_codes=language_hints,
            enable_automatic_punctuation=True,
        )

        audio = speech.RecognitionAudio(content=audio_bytes)

        # Use sync recognition for small audio; client can switch to long-running for longer recordings
        response = speech_client.recognize(config=config, audio=audio)

        transcript = " ".join([r.alternatives[0].transcript for r in response.results]) if response.results else ""

        if not transcript or len(transcript) < 2:
            logger.warning("⚠️ Empty or silent audio detected")
            transcript = "Couldn't catch that. Please try again."

        logger.info(f"📝 TRANSCRIBED TEXT: '{transcript}'")

        return {"status": "success", "transcript": transcript, "session_id": session_id}

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
        
        response = {
            "status": result.get("status", "completed"),
            "task_id": message.task_id,
            "text": response_text,  # This goes to TTS
            "result": result
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
        "transcription": "available (Google Speech-to-Text)" if speech_client else "unavailable",
        "tts": "available (Google Text-to-Speech)" if tts_client else "unavailable"
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
            if hasattr(message, 'session_id') and message.session_id == session_id:
                if hasattr(message, 'payload'):
                    # Forward the entire payload so clients can react to different actions
                    await thinking_queue.put(message.payload)
        
        # Subscribe to broadcast channel
        broker.subscribe(Channels.BROADCAST, handle_thinking_update)
        
        try:
            while True:
                try:
                    # Wait for thinking updates with timeout
                    payload = await asyncio.wait_for(thinking_queue.get(), timeout=30)
                    # Send full payload as JSON so clients can handle update/clear events
                    yield f"data: {json.dumps(payload)}\n\n"
                except asyncio.TimeoutError:
                    # Keep connection alive with heartbeat
                    yield ": heartbeat\n\n"
        except GeneratorExit:
            logger.info(f"🔌 Client disconnected from thinking stream: {session_id}")
        except Exception as e:
            logger.error(f"❌ Thinking stream error: {e}")
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/new-chat")
async def new_chat_endpoint(request: dict):
    """Handle new chat creation - clear session state"""
    try:
        session_id = request.get("session_id")
        user_id = request.get("user_id", "test_user")
        
        logger.info(f"🔄 New chat requested - clearing session: {session_id}")
        
        # Clear language agent conversation for this session
        from agents.language_agent import active_agents
        agent_key = f"{user_id}_{session_id}"
        
        if agent_key in active_agents:
            active_agents[agent_key].clear_conversation()
            logger.info(f"✅ Cleared language agent for {agent_key}")
        else:
            logger.info(f"ℹ️ No active agent found for {agent_key}")
        
        return {"status": "success", "message": "New chat started", "session_id": session_id}
        
    except Exception as e:
        logger.error(f"❌ New chat error: {e}")
        return {"status": "error", "message": str(e)}, 500

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

