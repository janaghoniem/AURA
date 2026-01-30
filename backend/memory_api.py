"""
Memory Management API Endpoints - UPDATED
Focused on Long-Term Memory (Preferences) Management
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
import logging
from datetime import datetime
from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/memory", tags=["memory"])

MONGODB_URI = os.getenv("MONGODB_URI")

@router.get("/preferences")
async def get_user_preferences(user_id: str, limit: int = 100):
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
                    "timestamp": pref.get("metadata", {}).get("timestamp", None),
                    "confidence": pref.get("metadata", {}).get("confidence", "unknown")
                })
        
        return {"preferences": formatted, "total": len(formatted)}
        
    except Exception as e:
        logger.error(f"❌ Failed to get preferences: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/clear-preferences")
async def clear_user_preferences(user_id: str):
    """Clear ALL long-term memory (preferences) for a user"""
    try:
        client = MongoClient(MONGODB_URI)
        db = client["yusr_db"]
        
        # Delete all preferences from mem0_preferences collection
        pref_result = db["mem0_preferences"].delete_many({"user_id": user_id})
        
        logger.warning(f"🗑️ CLEARED ALL PREFERENCES for user {user_id}")
        
        return {
            "status": "success",
            "preferences_deleted": pref_result.deleted_count,
            "message": f"Deleted {pref_result.deleted_count} preferences"
        }
        
    except Exception as e:
        logger.error(f"❌ Clear preferences failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_memory_stats(user_id: str):
    """Get preference statistics (no conversation history)"""
    try:
        client = MongoClient(MONGODB_URI)
        db = client["yusr_db"]
        
        # Count preferences by category
        preferences = db["mem0_preferences"]
        
        total_prefs = preferences.count_documents({"user_id": user_id})
        personal_info = preferences.count_documents({
            "user_id": user_id,
            "metadata.category": "personal_info"
        })
        app_usage = preferences.count_documents({
            "user_id": user_id,
            "metadata.category": "app_usage"
        })
        
        # Estimate storage size
        user_prefs = list(preferences.find({"user_id": user_id}))
        storage_size_mb = (len(str(user_prefs)) / (1024 * 1024))
        
        return {
            "total_preferences": total_prefs,
            "personal_info_count": personal_info,
            "app_preferences_count": app_usage,
            "storage_size_mb": round(storage_size_mb, 2)
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))