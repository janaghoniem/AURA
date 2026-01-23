"""
Thinking Step Manager - FIXED: Progressive step broadcasting
"""
import asyncio
from typing import List, Optional
from agents.utils.protocol import AgentMessage, MessageType, AgentType, Channels
from agents.utils.broker import broker
import logging

logger = logging.getLogger(__name__)

class ThinkingStepManager:
    active_sessions = {} # session_id -> { "history": [], "current": "" }

    @staticmethod
    async def update_step(session_id: str, step: str, message_id: str):
        """FIX: Add delay between steps for progressive display"""
        if session_id not in ThinkingStepManager.active_sessions:
            ThinkingStepManager.active_sessions[session_id] = {"history": []}
        
        session_data = ThinkingStepManager.active_sessions[session_id]
        
        # Check if step already exists to avoid duplicates
        if step in session_data["history"]:
            return
        
        # Add step to history
        session_data["history"].append(step)
        
        # Broadcast to frontend via broker
        update_msg = AgentMessage(
            message_type=MessageType.STATUS_UPDATE,
            sender=AgentType.COORDINATOR,
            receiver=AgentType.LANGUAGE,
            session_id=session_id,
            response_to=message_id,
            payload={
                "action": "thinking_update",
                "steps": session_data["history"],  # Send the whole list
                "session_id": session_id
            }
        )
        await broker.publish(Channels.BROADCAST, update_msg)
        
        # FIX: Add small delay for visual feedback (300ms feels natural)
        await asyncio.sleep(0.3)
    
    @staticmethod
    async def clear_steps(session_id: str):
        """Clear thinking steps for a session"""
        if session_id in ThinkingStepManager.active_sessions:
            del ThinkingStepManager.active_sessions[session_id]
            logger.info(f"🧠 [{session_id}] Cleared thinking steps")

# Thinking step sequences for different flows
THINKING_STEPS = {
    "language_agent": [
        "Analyzing your request...",
        "Checking clarifications...",
        "Preparing for coordinator...",
    ],
    "coordinator": [
        "Formulating plan...",
        "Decomposing tasks...",
        "Organizing execution order...",
    ],
    "execution_agent": [
        "Executing tasks...",
        "Processing actions...",
        "Collecting results...",
    ],
}