"""
YUSR Main Server - Pub/Sub Architecture with Groq TTS/STT
Starts all agents and provides HTTP API for Electron app
"""
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
from agents.execution_agent.Coordinator import start_execution_agent
from agents.utils.protocol import (
    AgentMessage, MessageType, AgentType, Channels,
    ClarificationMessage
)
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Store pending responses (for HTTP API)
pending_responses = {}

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
    logger.info("🚀 Starting YUSR Backend...")
    
    # Start broker
    await broker.start()
    
    # Subscribe to output channels BEFORE starting agents
    broker.subscribe(Channels.LANGUAGE_OUTPUT, handle_language_output)
    broker.subscribe(Channels.COORDINATOR_TO_LANGUAGE, handle_coordinator_output)
    
    # Start all agents concurrently
    asyncio.create_task(start_language_agent(broker))
    asyncio.create_task(start_coordinator_agent(broker))
    asyncio.create_task(start_execution_agent(broker))
    
    logger.info("✅ All agents started successfully")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down YUSR Backend...")
    await broker.stop()


app = FastAPI(
    title="YUSR Unified Backend (Pub/Sub)",
    description="Multi-agent system with message broker",
    version="3.0.0",
    lifespan=lifespan
)

# CORS for Electron
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    
    Automatically selects the appropriate voice based on text content:
    - Primarily Arabic text → orpheus-arabic-saudi
    - Primarily English text → orpheus-english
    - Mixed text → Uses the voice specified or defaults based on majority language
    
    Returns base64-encoded WAV audio
    """
    try:
        logger.info("🔊 Received TTS request")
        
        if not groq_client:
            logger.error("❌ Groq client not initialized")
            raise HTTPException(status_code=500, detail="TTS service not available - GROQ_API_KEY not set")
        
        data = await request.json()
        text = data.get("text", "").strip()
        voice_name = data.get("voice_name")  # Optional - auto-detect if not provided
        force_voice = data.get("force_voice", False)  # Override auto-detection
        
        if not text:
            logger.error("❌ No text provided for TTS")
            raise HTTPException(status_code=400, detail="Missing 'text' field")
        
        # Auto-detect language if voice not specified or not forcing
        if not voice_name or not force_voice:
            detected_lang = detect_language(text)
            logger.info(f"🔍 Detected language: {detected_lang}")
            
            if not force_voice:
                # Auto-select voice based on detected language
                if detected_lang == 'arabic':
                    voice_name = 'orpheus-arabic'
                    logger.info("🎤 Auto-selected Arabic voice")
                elif detected_lang == 'mixed':
                    # For mixed, prefer Arabic voice if more than 30% Arabic
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
        
        # Default to English if still not set
        if not voice_name:
            voice_name = 'orpheus-english'
        
        # Map voice names to Groq model IDs
        voice_mapping = {
            "orpheus-english": "orpheus-english",
            "orpheus-arabic": "orpheus-arabic-saudi",
            "arabic": "orpheus-arabic-saudi",  # Alias
            "english": "orpheus-english",  # Alias
            "Gacrux": "orpheus-english"  # Legacy fallback
        }
        
        groq_voice = voice_mapping.get(voice_name, "orpheus-english")
        
        logger.info(f"🗣️ Generating speech for text: '{text[:50]}...'")
        logger.info(f"🎤 Using voice: {groq_voice}")
        
        # Generate TTS using Groq
        response = groq_client.audio.speech.create(
            model=groq_voice,
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
            "sample_rate": 24000,  # Groq default
            "voice_used": groq_voice,
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
        
        if not user_input:
            raise HTTPException(status_code=400, detail="Missing 'input' field")
        
        logger.info(f"📥 HTTP request from session {session_id}: {user_input}")
        
        # Create message
        if is_clarification:
            # Clarification response - use "answer" key
            message = AgentMessage(
                message_type=MessageType.CLARIFICATION_RESPONSE,
                sender=AgentType.LANGUAGE,
                receiver=AgentType.LANGUAGE,
                session_id=session_id,
                payload={"answer": user_input, "input": user_input}  # Include both for compatibility
            )
            logger.info(f"💬 Created clarification response message")
            logger.info(f"💬 Payload: {message.payload}")
        else:
            # New task request - use "input" key
            message = AgentMessage(
                message_type=MessageType.TASK_REQUEST,
                sender=AgentType.LANGUAGE,
                receiver=AgentType.LANGUAGE,
                session_id=session_id,
                payload={"input": user_input}
            )
            logger.info(f"📋 Created task request message")
            logger.info(f"📋 Payload: {message.payload}")
        
        # IMPORTANT: Register pending response BEFORE publishing
        logger.info(f"⏳ Creating pending response for message ID: {message.message_id}")
        future = asyncio.Future()
        pending_responses[message.message_id] = future
        logger.info(f"📝 Registered pending response. Total pending: {len(pending_responses)}")
        logger.info(f"📝 Pending IDs: {list(pending_responses.keys())}")
        
        # Now publish to Language Agent
        logger.info(f"📤 Publishing message to {Channels.LANGUAGE_INPUT}")
        await broker.publish(Channels.LANGUAGE_INPUT, message)
        
        # Wait for response (with timeout)
        logger.info(f"⏰ Waiting up to 60s for response...")
        try:
            response = await asyncio.wait_for(future, timeout=60.0)
            logger.info(f"✅ Response received: {response}")
            return response
        except asyncio.TimeoutError:
            logger.error(f"❌ TIMEOUT waiting for response to message: {message.message_id}")
            logger.error(f"❌ Pending responses at timeout: {list(pending_responses.keys())}")
            raise HTTPException(status_code=504, detail="Request timeout")
        finally:
            # Clean up
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