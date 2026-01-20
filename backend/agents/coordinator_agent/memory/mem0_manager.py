"""
Mem0 Integration for Long-Term Preference Management
Uses MongoDB Atlas for vector storage (no local dependencies)
"""

import os
from typing import List, Dict, Optional
from mem0 import Memory
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)

class Mem0PreferenceManager:
    """Manages long-term user preferences using Mem0 with MongoDB Atlas backend"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        
        # Get MongoDB URI from environment
        MONGODB_URI = os.getenv("MONGODB_URI")
        if not MONGODB_URI:
            raise ValueError("MONGODB_URI not found in environment variables")
        
        # Extract connection details from URI
        # Format: mongodb+srv://user:pass@cluster.xxxxx.mongodb.net/dbname
        import urllib.parse
        parsed = urllib.parse.urlparse(MONGODB_URI)
        
        # Initialize Mem0 with MongoDB Atlas backend
        # Initialize Mem0 with MongoDB Atlas backend
        config = {
            "vector_store": {
                "provider": "mongodb",
                "config": {
                    "MONGODB_URI": MONGODB_URI,  # ← MUST BE "MONGODB_URI" not "url"
                    "db_name": "yusr_db",
                    "collection_name": "mem0_preferences",
                    "embedding_model_dims": 384
                }
            },
            "llm": {
                "provider": "groq",
                "config": {
                    "model": "llama-3.3-70b-versatile",
                    "temperature": 0.1,
                    "max_tokens": 2000,
                    "api_key": os.getenv("GROQ_API_KEY")
                }
            },
            "embedder": {
                "provider": "huggingface",
                "config": {
                    "model": "sentence-transformers/all-MiniLM-L6-v2"
                }
            }
        }
            #"history_db_path": None  # Use MongoDB, not local SQLite
        
        
        try:
            self.memory = Memory.from_config(config)
            logger.info(f"✅ Mem0 initialized for user {user_id} with MongoDB Atlas")
        except Exception as e:
            logger.error(f"❌ Mem0 initialization failed: {e}")
            raise
    
    def add_preference(self, preference: str, metadata: Optional[Dict] = None) -> str:
        """
        Store a user preference
        
        Args:
            preference: The preference text (e.g., "User prefers dark mode")
            metadata: Optional metadata (category, timestamp, etc.)
        
        Returns:
            Memory ID or None if failed
        """
        try:
            messages = [{"role": "user", "content": preference}]
            result = self.memory.add(
                messages=messages,
                user_id=self.user_id,
                metadata=metadata or {}
            )
            logger.info(f"✅ Stored preference for {self.user_id}: {preference[:50]}...")
            return result
        except Exception as e:
            logger.error(f"❌ Failed to store preference: {e}")
            return None
    
    def get_relevant_preferences(self, query: str, limit: int = 5) -> List[Dict]:
        try:
            memories = self.memory.search(
                query=query,
                user_id=self.user_id,
                limit=limit
            )

            logger.info(f"🔍 Mem0 raw response type: {type(memories)}")
            
            # Handle different Mem0 response formats
            if isinstance(memories, dict):
                # Format 1: {"results": [...]}
                if 'results' in memories:
                    memories = memories['results']
                # Format 2: {"memories": [...]}
                elif 'memories' in memories:
                    memories = memories['memories']
                # Format 3: Direct dict with memory field
                elif 'memory' in memories:
                    memories = [memories]
                else:
                    logger.warning(f"⚠️ Unknown Mem0 dict format: {list(memories.keys())}")
                    memories = []
            
            # Ensure it's a list
            if not isinstance(memories, list):
                logger.warning(f"⚠️ Expected list, got {type(memories)}")
                memories = []
            
            logger.info(f"✅ Processed {len(memories)} preferences for query: {query[:50]}...")
            return memories
        except Exception as e:
            logger.error(f"❌ Failed to retrieve preferences: {e}")
            return []


    def get_conversation_history(self, limit: int = 5) -> List:
        """
        Get recent conversation history for this user
        
        Args:
            limit: Maximum number of conversations to retrieve
        
        Returns:
            List of recent conversation contexts
        """
        try:
            # Get all memories for user
            all_memories = self.memory.get_all(user_id=self.user_id)
            
            # Filter for conversation_history category
            conversations = []
            for mem in all_memories:
                if isinstance(mem, dict):
                    category = mem.get('metadata', {}).get('category', '')
                    if category == 'conversation_history':
                        conversations.append(mem)
            
            # Sort by timestamp (most recent first)
            conversations.sort(
                key=lambda x: x.get('metadata', {}).get('timestamp', ''),
                reverse=True
            )
            
            logger.info(f"✅ Retrieved {len(conversations[:limit])} conversation histories")
            return conversations[:limit]
            
        except Exception as e:
            logger.error(f"❌ Failed to get conversation history: {e}")
            return []

    def get_all_preferences(self) -> List[Dict]:
        """Get all preferences for the user"""
        try:
            memories = self.memory.get_all(user_id=self.user_id)
            logger.info(f"✅ Retrieved {len(memories)} total preferences for {self.user_id}")
            return memories
        except Exception as e:
            logger.error(f"❌ Failed to get all preferences: {e}")
            return []
    
    def delete_preference(self, memory_id: str) -> bool:
        """Delete a specific preference"""
        try:
            self.memory.delete(memory_id=memory_id)
            logger.info(f"✅ Deleted preference {memory_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to delete preference: {e}")
            return False
    
    def format_for_llm(self, preferences: List) -> str:
        """Format preferences for injection into LLM prompt"""
        if not preferences:
            return "No stored user preferences."
        
        formatted = "# USER PREFERENCES (FROM PREVIOUS SESSIONS)\n"
        for i, pref in enumerate(preferences, 1):
            # Mem0 returns memories in different formats depending on version
            if isinstance(pref, str):
                memory_text = pref
            elif isinstance(pref, dict):
                memory_text = pref.get('memory', pref.get('text', pref.get('content', 'Unknown')))
            else:
                memory_text = str(pref)
            formatted += f"{i}. {memory_text}\n"
        
        return formatted

# Factory function for easy access
_preference_managers: Dict[str, Mem0PreferenceManager] = {}

def get_preference_manager(user_id: str) -> Mem0PreferenceManager:
    """Get or create preference manager for user"""
    if user_id not in _preference_managers:
        _preference_managers[user_id] = Mem0PreferenceManager(user_id)
    return _preference_managers[user_id]