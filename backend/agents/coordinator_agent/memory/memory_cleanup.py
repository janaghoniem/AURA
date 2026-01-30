"""
Memory Cleanup Service - Prevents MongoDB bloat
Run this periodically (e.g., daily cron job)
"""

import os
import logging
from datetime import datetime, timedelta
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

MONGODB_URI = os.getenv("MONGODB_URI")

def cleanup_old_conversations(days_to_keep: int = 30):
    """Delete conversations older than N days"""
    try:
        client = MongoClient(MONGODB_URI)
        db = client["yusr_db"]
        conversations = db["language_agent_conversations"]
        
        cutoff_timestamp = (datetime.now() - timedelta(days=days_to_keep)).timestamp()
        
        result = conversations.delete_many({
            "timestamp": {"$lt": cutoff_timestamp}
        })
        
        logger.info(f"✅ Deleted {result.deleted_count} conversations older than {days_to_keep} days")
        
    except Exception as e:
        logger.error(f"❌ Cleanup failed: {e}")

def cleanup_old_checkpoints(days_to_keep: int = 7):
    """Delete old LangGraph checkpoints"""
    try:
        client = MongoClient(MONGODB_URI)
        db = client["yusr_db"]
        checkpoints = db["langgraph_checkpoints"]
        
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        # LangGraph stores timestamps differently, adjust as needed
        result = checkpoints.delete_many({
            "metadata.created_at": {"$lt": cutoff_date.isoformat()}
        })
        
        logger.info(f"✅ Deleted {result.deleted_count} checkpoints older than {days_to_keep} days")
        
    except Exception as e:
        logger.error(f"❌ Checkpoint cleanup failed: {e}")

def trim_conversation_history_per_session(max_messages: int = 50):
    """Keep only last N messages per session"""
    try:
        client = MongoClient(MONGODB_URI)
        db = client["yusr_db"]
        conversations = db["language_agent_conversations"]
        
        # Get all sessions
        sessions = conversations.distinct("session_id")
        
        updated_count = 0
        for session_id in sessions:
            doc = conversations.find_one({"session_id": session_id})
            if doc and "messages" in doc:
                messages = doc["messages"]
                
                if len(messages) > max_messages:
                    # Keep system prompt + last N messages
                    system_prompt = messages[0] if messages[0].get("role") == "system" else None
                    trimmed = messages[-max_messages:]
                    
                    if system_prompt:
                        trimmed.insert(0, system_prompt)
                    
                    conversations.update_one(
                        {"session_id": session_id},
                        {"$set": {"messages": trimmed}}
                    )
                    updated_count += 1
                    logger.debug(f"Trimmed session {session_id}: {len(messages)} → {len(trimmed)} messages")
        
        logger.info(f"✅ Trimmed {updated_count} sessions to {max_messages} messages each")
        
    except Exception as e:
        logger.error(f"❌ Trim failed: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("🧹 Running memory cleanup...")
    cleanup_old_conversations(days_to_keep=30)
    cleanup_old_checkpoints(days_to_keep=7)
    trim_conversation_history_per_session(max_messages=50)
    print("✅ Cleanup complete!")