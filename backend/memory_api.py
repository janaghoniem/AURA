"""
Memory Management API Endpoints
Connects Settings Modal to memory_cleanup.py functionality
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
import logging
from datetime import datetime, timedelta
from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/memory", tags=["memory"])

MONGODB_URI = os.getenv("MONGODB_URI")

class MemoryStats(BaseModel):
    total_conversations: int
    total_preferences: int
    total_checkpoints: int
    oldest_conversation: Optional[str]
    storage_size_mb: float

class CleanupConfig(BaseModel):
    max_conversation_days: int = 30
    max_checkpoint_days: int = 7
    max_messages_per_session: int = 50

@router.get("/stats", response_model=MemoryStats)
async def get_memory_stats(user_id: str):
    """Get current memory usage statistics"""
    try:
        client = MongoClient(MONGODB_URI)
        db = client["yusr_db"]
        
        # Count documents
        conversations = db["language_agent_conversations"]
        preferences = db["mem0_preferences"]
        checkpoints = db["langgraph_checkpoints"]
        
        conv_count = conversations.count_documents({"user_id": user_id})
        pref_count = preferences.count_documents({"user_id": user_id})
        checkpoint_count = checkpoints.count_documents({})
        
        # Get oldest conversation
        oldest_conv = conversations.find_one(
            {"user_id": user_id},
            sort=[("timestamp", 1)]
        )
        oldest_date = None
        if oldest_conv and "timestamp" in oldest_conv:
            oldest_date = datetime.fromtimestamp(oldest_conv["timestamp"]).isoformat()
        
        # Estimate storage size (rough)
        db_stats = db.command("dbStats")
        storage_size_mb = db_stats.get("dataSize", 0) / (1024 * 1024)
        
        return MemoryStats(
            total_conversations=conv_count,
            total_preferences=pref_count,
            total_checkpoints=checkpoint_count,
            oldest_conversation=oldest_date,
            storage_size_mb=round(storage_size_mb, 2)
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to get memory stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cleanup")
async def cleanup_memory(config: CleanupConfig, user_id: str):
    """Clean up old memories based on configuration"""
    try:
        client = MongoClient(MONGODB_URI)
        db = client["yusr_db"]
        
        results = {
            "conversations_deleted": 0,
            "checkpoints_deleted": 0,
            "sessions_trimmed": 0
        }
        
        # 1. Delete old conversations
        conversations = db["language_agent_conversations"]
        cutoff_timestamp = (datetime.now() - timedelta(days=config.max_conversation_days)).timestamp()
        
        conv_result = conversations.delete_many({
            "user_id": user_id,
            "timestamp": {"$lt": cutoff_timestamp}
        })
        results["conversations_deleted"] = conv_result.deleted_count
        
        # 2. Delete old checkpoints
        checkpoints = db["langgraph_checkpoints"]
        checkpoint_cutoff = datetime.now() - timedelta(days=config.max_checkpoint_days)
        
        checkpoint_result = checkpoints.delete_many({
            "metadata.created_at": {"$lt": checkpoint_cutoff.isoformat()}
        })
        results["checkpoints_deleted"] = checkpoint_result.deleted_count
        
        # 3. Trim conversation history
        user_sessions = conversations.find({"user_id": user_id})
        
        for session_doc in user_sessions:
            if "messages" in session_doc:
                messages = session_doc["messages"]
                
                if len(messages) > config.max_messages_per_session:
                    # Keep system prompt + last N messages
                    system_prompt = messages[0] if messages[0].get("role") == "system" else None
                    trimmed = messages[-config.max_messages_per_session:]
                    
                    if system_prompt:
                        trimmed.insert(0, system_prompt)
                    
                    conversations.update_one(
                        {"_id": session_doc["_id"]},
                        {"$set": {"messages": trimmed}}
                    )
                    results["sessions_trimmed"] += 1
        
        logger.info(f"✅ Cleanup completed: {results}")
        return results
        
    except Exception as e:
        logger.error(f"❌ Cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/clear-all")
async def clear_all_memories(user_id: str):
    """Clear ALL memories for a user (DANGEROUS)"""
    try:
        client = MongoClient(MONGODB_URI)
        db = client["yusr_db"]
        
        # Delete all conversations
        conv_result = db["language_agent_conversations"].delete_many({"user_id": user_id})
        
        # Delete all preferences
        pref_result = db["mem0_preferences"].delete_many({"user_id": user_id})
        
        logger.warning(f"🗑️ CLEARED ALL MEMORIES for user {user_id}")
        
        return {
            "conversations_deleted": conv_result.deleted_count,
            "preferences_deleted": pref_result.deleted_count
        }
        
    except Exception as e:
        logger.error(f"❌ Clear all failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/preferences")
async def get_user_preferences(user_id: str, limit: int = 50):
    """Get all stored preferences for a user"""
    try:
        from agents.coordinator_agent.memory.mem0_manager import get_preference_manager
        
        pref_mgr = get_preference_manager(user_id)
        all_prefs = pref_mgr.get_all_preferences()
        
        # Format for frontend
        formatted = []
        for pref in all_prefs[:limit]:
            if isinstance(pref, dict):
                formatted.append({
                    "id": pref.get("id", "unknown"),
                    "text": pref.get("memory", pref.get("text", "Unknown")),
                    "category": pref.get("metadata", {}).get("category", "general"),
                    "timestamp": pref.get("metadata", {}).get("timestamp", "unknown")
                })
        
        return {"preferences": formatted}
        
    except Exception as e:
        logger.error(f"❌ Failed to get preferences: {e}")
        raise HTTPException(status_code=500, detail=str(e))