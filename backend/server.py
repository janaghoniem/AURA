"""
YUSR Main Server - Pub/Sub Architecture
Starts all agents and provides HTTP API for Electron app
"""
import asyncio
import logging
import os
import base64
import tempfile
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from google import genai

# Import broker and agents
from agents.utils.broker import broker
from agents.language_agent import start_language_agent
from agents.coordinator_agent.coordinator_agent import start_coordinator_agent
from agents.execution_agent.Coordinator import start_execution_agent
from agents.utils.protocol import (
    AgentMessage, MessageType, AgentType, Channels,
    ClarificationMessage
)

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
            logger.info(f"📊 File state: {uploaded_file.state}")

            # Wait for file to become ACTIVE
            import time
            max_wait = 30  # seconds
            wait_time = 0
            while uploaded_file.state.name != "ACTIVE" and wait_time < max_wait:
                logger.info(f"⏳ Waiting for file to become ACTIVE... (current state: {uploaded_file.state.name})")
                time.sleep(2)
                wait_time += 2
                uploaded_file = genai_client.files.get(name=uploaded_file.name)

            if uploaded_file.state.name != "ACTIVE":
                logger.error(f"❌ File failed to become ACTIVE after {max_wait}s. State: {uploaded_file.state.name}")
                raise Exception(f"File processing timeout. State: {uploaded_file.state.name}")

            logger.info("✅ File is ACTIVE, starting transcription")

            # Generate transcript
            prompt = "Generate a transcript of the speech. Return ONLY the transcript text, nothing else."
            response = genai_client.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=[prompt, uploaded_file]
            )

            transcript = response.text.strip()

            if not transcript:
                logger.warning("⚠️ Transcription returned EMPTY text!")
                transcript = "[Empty transcription - no speech detected]"
            else:
                logger.info(f"✅ Transcription successful! 📝: {transcript}")

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
            # Clarification response
            message = AgentMessage(
                message_type=MessageType.CLARIFICATION_RESPONSE,
                sender=AgentType.LANGUAGE,
                receiver=AgentType.LANGUAGE,
                session_id=session_id,
                payload={"answer": user_input}
            )
            logger.info(f"💬 Created clarification response message")
        else:
            # New task request
            message = AgentMessage(
                message_type=MessageType.TASK_REQUEST,
                sender=AgentType.LANGUAGE,
                receiver=AgentType.LANGUAGE,
                session_id=session_id,
                payload={"input": user_input}
            )
            logger.info(f"📋 Created task request message")
        
        # Publish to Language Agent
        logger.info(f"📤 Publishing message to {Channels.LANGUAGE_INPUT}")
        await broker.publish(Channels.LANGUAGE_INPUT, message)
        
        # Wait for response (with timeout)
        logger.info(f"⏳ Waiting for response (timeout: 30s)...")
        response = await wait_for_response(message.message_id, timeout=30.0)
        logger.info(f"✅ Response received: {response}")
        
        return response
    
    except asyncio.TimeoutError:
        logger.error("❌ Request timeout - no response from agents")
        raise HTTPException(status_code=504, detail="Request timeout")
    except Exception as e:
        logger.error(f"❌ Error processing request: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def wait_for_response(message_id: str, timeout: float = 30.0):
    """Wait for agent response"""
    # Create a future to wait for
    future = asyncio.Future()
    pending_responses[message_id] = future
    
    try:
        # Wait for response with timeout
        response = await asyncio.wait_for(future, timeout=timeout)
        return response
    finally:
        # Clean up
        pending_responses.pop(message_id, None)


async def handle_language_output(message: AgentMessage):
    """Handle output from Language Agent"""
    logger.info(f"📨 Received from Language Agent: {message.message_type}")
    
    if message.message_type == MessageType.CLARIFICATION_REQUEST:
        # Clarification needed
        response_content = {
            "status": "clarification_needed",
            "question": message.payload.get("question", "Need more information."),
            "response_id": message.message_id
        }
        
        logger.info(f"❓ Clarification needed: {response_content['question']}")
        
        # Resolve the future
        target_id = message.response_to
        if target_id and target_id in pending_responses:
            logger.info(f"✅ Resolving pending request: {target_id}")
            pending_responses[target_id].set_result(response_content)
        else:
            logger.warning(f"⚠️ No pending response found for: {target_id}")


async def handle_coordinator_output(message: AgentMessage):
    """Handle output from Coordinator"""
    logger.info(f"📨 Received from Coordinator: {message.message_type}")
    
    if message.message_type == MessageType.TASK_RESPONSE:
        # Task completed
        result = message.payload
        response = {
            "status": "completed",
            "task_id": message.task_id,
            "result": result
        }
        
        logger.info(f"✅ Task completed: {message.task_id}")
        
        # Find the original message ID
        for msg_id, future in list(pending_responses.items()):
            if not future.done():
                logger.info(f"✅ Resolving pending request: {msg_id}")
                future.set_result(response)
                break
    
    elif message.message_type == MessageType.ERROR:
        # Error occurred
        response = {
            "status": "error",
            "error": message.payload.get("error"),
            "details": message.payload.get("details", "")
        }
        
        logger.error(f"❌ Error from coordinator: {response['error']}")
        
        for msg_id, future in list(pending_responses.items()):
            if not future.done():
                logger.info(f"✅ Resolving pending request with error: {msg_id}")
                future.set_result(response)
                break


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
        "transcription": "available" if genai_client else "unavailable"
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