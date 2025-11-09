"""
YUSR Main Server - Pub/Sub Architecture
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
from google import genai
from google.genai import types

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

# Initialize Google Genai Client
API_KEY = os.environ.get("GOOGLE_API_KEY")
if not API_KEY:
    logger.warning("⚠️ GOOGLE_API_KEY not set - speech transcription will not work")
    genai_client = None
else:
    genai_client = genai.Client(api_key=API_KEY)
    logger.info("✅ Google Genai client initialized")


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

@app.post("/text-to-speech")
async def text_to_speech(request: Request):
    """
    Convert text to speech using Google Gemini TTS
    
    Returns base64-encoded WAV audio
    """
    try:
        logger.info("🔊 Received TTS request")
        
        if not genai_client:
            logger.error("❌ Google Genai client not initialized")
            raise HTTPException(status_code=500, detail="TTS service not available - GOOGLE_API_KEY not set")
        
        data = await request.json()
        text = data.get("text", "").strip()
        voice_name = data.get("voice_name", "Gacrux")  # Default voice
        
        if not text:
            logger.error("❌ No text provided for TTS")
            raise HTTPException(status_code=400, detail="Missing 'text' field")
        
        logger.info(f"🗣️ Generating speech for text: '{text[:50]}...'")
        logger.info(f"🎤 Using voice: {voice_name}")
        
        # Generate TTS
        response = genai_client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice_name
                        )
                    )
                ),
            ),
        )
        
        # Extract PCM bytes
        pcm_data = response.candidates[0].content.parts[0].inline_data.data
        logger.info(f"✅ TTS generated: {len(pcm_data)} bytes of PCM data")
        
        # Convert raw PCM to WAV in memory
        rate = 24000  # Hz
        channels = 1
        sample_width = 2  # bytes (16-bit)
        buffer = io.BytesIO()
        
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(rate)
            wf.writeframes(pcm_data)
        
        buffer.seek(0)
        wav_bytes = buffer.read()
        
        # Convert to base64
        base64_audio = base64.b64encode(wav_bytes).decode('utf-8')
        logger.info(f"✅ WAV created and encoded: {len(base64_audio)} base64 characters")
        
        return {
            "status": "success",
            "audio_data": base64_audio,
            "format": "wav",
            "sample_rate": rate
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ TTS error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"TTS failed: {str(e)}")


@app.post("/transcribe")
async def transcribe_audio(request: Request):
    """
    Transcribe WAV audio using Google Gemini API
    
    Accepts base64-encoded .wav audio data, transcribes it, and returns the text.
    """
    try:
        logger.info("🎤 Received audio transcription request")

        if not genai_client:
            logger.error("❌ Google Genai client not initialized")
            raise HTTPException(status_code=500, detail="Transcription service not available - GOOGLE_API_KEY not set")

        data = await request.json()
        audio_data = data.get("audio_data", "")
        session_id = data.get("session_id", "default")

        if not audio_data:
            logger.error("❌ No audio data provided")
            raise HTTPException(status_code=400, detail="Missing 'audio_data' field")

        logger.info(f"🔊 Processing audio for session: {session_id}")
        logger.info(f"📊 Audio data size: {len(audio_data)} bytes (base64)")

        # Decode base64 audio
        try:
            audio_bytes = base64.b64decode(audio_data)
            logger.info(f"✅ Decoded audio: {len(audio_bytes)} bytes")

            if len(audio_bytes) < 100:
                logger.error(f"❌ Audio file too small ({len(audio_bytes)} bytes) - likely empty or corrupt")
                raise HTTPException(status_code=400, detail="Audio file is empty or too small")

        except Exception as e:
            logger.error(f"❌ Failed to decode base64 audio: {e}")
            raise HTTPException(status_code=400, detail="Invalid base64 audio data")

        # Save to temporary WAV file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
            temp_file.write(audio_bytes)
            temp_path = temp_file.name
            logger.info(f"💾 Saved WAV audio to: {temp_path}")
            logger.info(f"📁 File size on disk: {os.path.getsize(temp_path)} bytes")

        try:
            # Upload file to Google GenAI
            logger.info("⬆️ Uploading WAV audio to Google GenAI...")
            uploaded_file = genai_client.files.upload(file=temp_path)
            logger.info(f"✅ File uploaded: {uploaded_file.name}")
            logger.info(f"📊 File state immediately after upload: {uploaded_file.state.name}")

            # Wait for file to become ACTIVE
            max_wait = 30  # seconds
            wait_time = 0
            while uploaded_file.state.name != "ACTIVE" and wait_time < max_wait:
                logger.info(f"⏳ Waiting for file to become ACTIVE... (current state: {uploaded_file.state.name}, waited {wait_time}s)")
                time.sleep(2)
                wait_time += 2
                uploaded_file = genai_client.files.get(name=uploaded_file.name)
                logger.info(f"📊 File state after refresh: {uploaded_file.state.name}")

            if uploaded_file.state.name != "ACTIVE":
                logger.error(f"❌ File failed to become ACTIVE after {max_wait}s. State: {uploaded_file.state.name}")
                raise Exception(f"File processing timeout. State: {uploaded_file.state.name}")

            logger.info("✅ File is ACTIVE, starting transcription")

            # Generate transcript
            prompt = """
You are a bilingual (Arabic + English) speech transcription system.

Your goals:
1. Transcribe the audio exactly as spoken.
2. Keep all Arabic and English words as-is. Do NOT translate or correct them.
3. If a clear command or app name appears (e.g. "open calculator", "افتح calendar", "شغل music"):
   - Keep the app or command name exactly in English as said.
   - Do not remove or replace any surrounding Arabic words.
4. If the user is speaking casually or having a normal conversation, just transcribe it as-is.
5. If the audio is silent, too noisy, or no words are detected, respond exactly with:
   "Couldn't catch that. Please try again."

Formatting rules:
- Output ONLY the raw transcript, nothing else.
- Keep Arabic and English mixed sentences in their original order.
- Do NOT add punctuation, translate, or summarize.

Examples:
- "افتح الكاميرا" → "افتح الكاميرا"
- "افتح calculator" → "افتح calculator"
- "I was just testing the mic" → "I was just testing the mic"
- "افتح calculator بسرعة" → "افتح calculator بسرعة"
- (silent audio) → "Couldn't catch that. Please try again."
"""

            response = genai_client.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=[prompt, uploaded_file]
            )

            transcript = response.text.strip()

            if not transcript:
                logger.warning("⚠️ Transcription returned EMPTY text!")
                transcript = "[Empty transcription - no speech detected]"
            else:
                logger.info(f"✅ Transcription successful!")
                logger.info(f"📝 TRANSCRIBED TEXT: '{transcript}'")

            # Clean up uploaded file
            try:
                genai_client.files.delete(name=uploaded_file.name)
                logger.info(f"🗑️ Deleted uploaded file from Google: {uploaded_file.name}")
            except Exception as e:
                logger.warning(f"⚠️ Could not delete uploaded file: {e}")

            return {
                "status": "success",
                "transcript": transcript,
                "session_id": session_id
            }

        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_path)
                logger.info(f"🗑️ Deleted temporary WAV file: {temp_path}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to delete temp file: {e}")

    except HTTPException:
        raise
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
        "transcription": "available" if genai_client else "unavailable",
        "tts": "available" if genai_client else "unavailable"
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