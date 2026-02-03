"""
Thinking Step Manager - Tracks and broadcasts thinking progress
"""
import asyncio
import logging
from typing import Optional
from agents.utils.protocol import AgentMessage, MessageType, AgentType, Channels
from agents.utils.broker import broker

logger = logging.getLogger(__name__)

class ThinkingStepManager:
    """Manages thinking step updates across agents"""
    
    # Global thinking steps being tracked
    active_sessions = {}  # session_id -> current_step
    
    @staticmethod
    async def update_step(session_id: str, step: str, message_id: str):
        """
        Update thinking step for a session
        
        Args:
            session_id: Session ID
            step: Current step (e.g., "Processing input...", "Analyzing request...", etc)
            message_id: Original HTTP request message ID
        """
        logger.info(f"🧠 [{session_id}] Thinking step: {step}")
        
        # Store current step
        ThinkingStepManager.active_sessions[session_id] = step
        
        # Broadcast to frontend via broker
        try:
            update_msg = AgentMessage(
                message_type=MessageType.STATUS_UPDATE,
                sender=AgentType.COORDINATOR,
                receiver=AgentType.LANGUAGE,
                session_id=session_id,
                response_to=message_id,
                payload={
                    "action": "thinking_update",
                    "step": step,
                    "session_id": session_id
                }
            )
            
            await broker.publish(Channels.BROADCAST, update_msg)
        except Exception as e:
            logger.warning(f"⚠️ Failed to broadcast thinking update: {e}")
    
    @staticmethod
    async def clear_steps(session_id: str):
        """Clear thinking steps for a session"""
        if session_id in ThinkingStepManager.active_sessions:
            del ThinkingStepManager.active_sessions[session_id]
            logger.info(f"🧠 [{session_id}] Cleared thinking steps")

        # Broadcast a clear message so clients can remove UI indicators
        try:
            clear_msg = AgentMessage(
                message_type=MessageType.STATUS_UPDATE,
                sender=AgentType.COORDINATOR,
                receiver=AgentType.LANGUAGE,
                session_id=session_id,
                payload={
                    "action": "thinking_clear",
                    "session_id": session_id
                }
            )
            await broker.publish(Channels.BROADCAST, clear_msg)
            logger.info(f"🧠 [{session_id}] Broadcasted thinking_clear to clients")
        except Exception as e:
            logger.warning(f"⚠️ Failed to broadcast thinking_clear: {e}")