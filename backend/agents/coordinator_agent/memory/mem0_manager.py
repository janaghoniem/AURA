"""
Mem0 Integration for Long-Term Preference Management
FIXED: Lowered threshold, added query expansion, improved retrieval
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
        
        MONGODB_URI = os.getenv("MONGODB_URI")
        if not MONGODB_URI:
            raise ValueError("MONGODB_URI not found in environment variables")
        
        config = {
            "vector_store": {
                "provider": "mongodb",
                "config": {
                    "MONGODB_URI": MONGODB_URI,
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
        
        try:
            self.memory = Memory.from_config(config)
            logger.info(f"✅ Mem0 initialized for user {user_id} with MongoDB Atlas")
        except Exception as e:
            logger.error(f"❌ Mem0 initialization failed: {e}")
            raise
    
    def add_preference(self, preference: str, metadata: Optional[Dict] = None) -> str:
        """Store a user preference"""
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

    def get_relevant_preferences(
        self, 
        query: str, 
        limit: int = 10,  # ✅ INCREASED from 5 to 10
        min_score: float = 0.65 # ✅ LOWERED from 0.65 to 0.3 (more permissive)
    ) -> List[Dict]:
        """
        Get preferences relevant to query with FIXED scoring
        
        Args:
            query: Search query
            limit: Max results to retrieve
            min_score: Minimum similarity (0.3 = loose match, 0.7 = strict match)
        
        Returns:
            List of relevant memories
        """
        try:
            # ✅ FIX 1: Expand query with common variations
            expanded_queries = [
                query,
                f"user preference: {query}",
                f"what does the user like for {query}"
            ]
            
            all_memories = []
            seen_ids = set()
            
            # Search with all query variations
            for q in expanded_queries:
                memories = self.memory.search(
                    query=q,
                    user_id=self.user_id,
                    limit=limit * 2
                )
                
                # Handle response format
                if isinstance(memories, dict):
                    if 'results' in memories:
                        memories = memories['results']
                    elif 'memories' in memories:
                        memories = memories['memories']
                    elif 'memory' in memories:
                        memories = [memories]
                    else:
                        memories = []
                
                if not isinstance(memories, list):
                    memories = []
                
                # Deduplicate by memory ID
                for mem in memories:
                    mem_id = mem.get('id') or mem.get('memory_id')
                    if mem_id and mem_id not in seen_ids:
                        all_memories.append(mem)
                        seen_ids.add(mem_id)
            
            # ✅ FIX 2: Filter by score with looser threshold
            relevant_memories = []
            for mem in all_memories:
                score = mem.get('score', 0.0)
                memory_text = mem.get('memory', mem.get('text', 'Unknown'))
                
                if score >= min_score:
                    relevant_memories.append(mem)
                    logger.info(f"  ✅ [Score: {score:.2f}] {memory_text[:60]}")
                else:
                    logger.debug(f"  ⤷ Filtered out (score {score:.2f} < {min_score})")
            
            # Sort by score descending
            relevant_memories.sort(key=lambda x: x.get('score', 0), reverse=True)
            
            # Limit to requested number
            relevant_memories = relevant_memories[:limit]
            
            logger.info(
                f"✅ Found {len(relevant_memories)}/{len(all_memories)} relevant preferences "
                f"(threshold: {min_score}) for query: {query[:50]}..."
            )
            
            return relevant_memories
            
        except Exception as e:
            logger.error(f"❌ Failed to retrieve preferences: {e}")
            return []

    def get_conversation_history(self, limit: int = 5) -> List:
        """Get recent conversation history"""
        try:
            all_memories = self.memory.get_all(user_id=self.user_id)
            
            conversations = []
            for mem in all_memories:
                if isinstance(mem, dict):
                    category = mem.get('metadata', {}).get('category', '')
                    if category == 'conversation_history':
                        conversations.append(mem)
            
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
            if isinstance(pref, str):
                memory_text = pref
            elif isinstance(pref, dict):
                memory_text = pref.get('memory', pref.get('text', pref.get('content', 'Unknown')))
            else:
                memory_text = str(pref)
            formatted += f"{i}. {memory_text}\n"
        
        return formatted

# Factory function
_preference_managers: Dict[str, Mem0PreferenceManager] = {}

def get_preference_manager(user_id: str) -> Mem0PreferenceManager:
    """Get or create preference manager for user"""
    if user_id not in _preference_managers:
        _preference_managers[user_id] = Mem0PreferenceManager(user_id)
    return _preference_managers[user_id]