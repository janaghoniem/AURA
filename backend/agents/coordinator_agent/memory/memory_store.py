# from langchain.memory import ConversationBufferMemory
# from langchain_community.vectorstores import FAISS
# from langchain_community.embeddings import HuggingFaceEmbeddings

# def get_short_term_memory():
#     return ConversationBufferMemory(memory_key="conversation_history", return_messages=True)

# def get_long_term_memory():
#     embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
#     texts = [
#         "User prefers minimalistic UIs.",
#         "Assistive commands should be simple and voice-driven.",
#         "YUSR is built for users with sight and mobility disabilities."
#     ]
#     vectorstore = FAISS.from_texts(texts, embeddings)
#     return vectorstore.as_retriever()

#---commented out by shahd----

#added by shahd
"""
LangGraph Memory System for YUSR Coordinator
Three-tier memory: working, short-term, long-term
"""

import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from langchain_core.documents import Document
from langchain_chroma import Chroma
#from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

# --- WORKING MEMORY (Task-scoped) ---
class WorkingMemory:
    """Holds context for current multi-step task execution"""
    def __init__(self):
        self.current_task_plan: Optional[Dict] = None
        self.task_outputs: Dict[str, Any] = {}  # Maps task_id → output
        self.execution_history: List[str] = []  # Chronological actions
    
    def start_task(self, plan: Dict):
        """Initialize for new task"""
        self.current_task_plan = plan
        self.task_outputs.clear()
        self.execution_history.clear()
    
    def log_step(self, task_id: str, action: str, result: Any):
        """Record execution step"""
        self.task_outputs[task_id] = result
        self.execution_history.append(f"{action}: {result.get('status', 'unknown')}")
    
    def get_context_summary(self) -> str:
        """Generate summary for LLM context"""
        if not self.execution_history:
            return "No execution history yet."
        return "\n".join(f"- {step}" for step in self.execution_history[-5:])
    
    def clear(self):
        """Reset after task completion"""
        self.current_task_plan = None
        self.task_outputs.clear()
        self.execution_history.clear()


# --- SHORT-TERM MEMORY (Session-scoped) ---
class ShortTermMemory:
    """Sliding window of recent tasks within session"""
    def __init__(self, window_size: int = 5):
        self.window_size = window_size
        self.recent_tasks: List[Dict] = []  # [{task, result, timestamp}]
    
    def add_task(self, task_description: str, result_summary: str):
        """Add completed task to history"""
        entry = {
            "task": task_description,
            "result": result_summary,
            "timestamp": datetime.now().isoformat()
        }
        self.recent_tasks.append(entry)
        
        # Prune if exceeds window
        if len(self.recent_tasks) > self.window_size:
            self.recent_tasks.pop(0)
    
    def get_recent_context(self, n: int = 3) -> str:
        """Get last n tasks as string"""
        if not self.recent_tasks:
            return "No recent tasks in this session."
        
        recent = self.recent_tasks[-n:]
        context_lines = []
        for entry in recent:
            context_lines.append(f"- {entry['task']} → {entry['result']}")
        return "\n".join(context_lines)
    
    def clear_session(self):
        """Called on 'start new chat'"""
        self.recent_tasks.clear()


# --- LONG-TERM MEMORY (Cross-session preferences) ---
class LongTermMemory:
    """Vector store for user preferences and learned patterns"""
    def __init__(self, user_id: str, persist_directory: str = "./chroma_db"):
        self.user_id = user_id
        
        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}

        )
        
        self.vectorstore = Chroma(
            collection_name="yusr_universal_memory",
            embedding_function=embeddings,
            persist_directory=os.path.abspath(persist_directory)
        )
    
    def add_memory(self, content: str, metadata: Dict = None):
        """Dynamically add a new memory/fact to the vector store"""
        if metadata is None: metadata = {}
        metadata.update({"user_id": self.user_id, "timestamp": datetime.now().isoformat()})
        
        doc = Document(page_content=content, metadata=metadata)
        self.vectorstore.add_documents([doc])
    
    def store_preference(self, preference: str, category: str):
        """Store user preference/pattern"""
        doc = Document(
            page_content=preference,
            metadata={
                "user_id": self.user_id,
                "category": category,
                "timestamp": datetime.now().isoformat()
            }
        )
        self.vectorstore.add_documents([doc])
    
    def get_relevant_context(self, query: str, k: int = 3) -> str:
        """Retrieve top-k relevant memories using semantic search"""
        if not query or query.strip() == "":
            return "No search query provided."

        # Search without strict user_id filtering first to ensure we get results
        results = self.vectorstore.similarity_search(query, k=k)
        
        if not results:
            return "No relevant past memories found."
        
        # Format the found memories for the LLM
        context_lines = [f"Past event: {doc.page_content}" for doc in results]
        return "\n".join(context_lines)
    
    
    def prune_old_entries(self, days: int = 90):
        """Remove entries older than N days"""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        # Chroma doesn't have built-in TTL, manual filter required
        all_docs = self.vectorstore.get()
        old_ids = [
            doc_id for doc_id, metadata in zip(all_docs['ids'], all_docs['metadatas'])
            if metadata.get('timestamp', '') < cutoff
        ]
        
        if old_ids:
            self.vectorstore.delete(ids=old_ids)


# --- MEMORY MANAGER (Singleton per user session) ---
class MemoryManager:
    """Orchestrates all memory tiers"""
    def __init__(self, user_id: str, session_id: str):
        self.user_id = user_id
        self.session_id = session_id
        
        self.working = WorkingMemory()
        self.short_term = ShortTermMemory(window_size=5)
        self.long_term = LongTermMemory(user_id)
    
    def get_full_context_for_llm(self, current_query: str) -> str:
        """Compile context from all memory tiers for LLM prompt"""
        sections = []
        
        # Working memory (current task)
        working_ctx = self.working.get_context_summary()
        if working_ctx != "No execution history yet.":
            sections.append(f"## Current Task Progress\n{working_ctx}")
        
        # Short-term memory (recent tasks)
        recent_ctx = self.short_term.get_recent_context(n=3)
        if recent_ctx != "No recent tasks in this session.":
            sections.append(f"## Recent Session History\n{recent_ctx}")
        
        # Long-term memory (user preferences)
        longterm_ctx = self.long_term.get_relevant_context(current_query, k=3)
        if longterm_ctx != "No stored preferences found.":
            sections.append(f"## User Preferences\n{longterm_ctx}")
        
        return "\n\n".join(sections) if sections else "No previous context available."
    
    def start_new_chat(self):
        """Reset session-scoped memory"""
        self.working.clear()
        self.short_term.clear_session()
        # Long-term memory persists across sessions
    
    async def get_summarized_context(self, llm) -> str:
        """Compress memory via LLM if too large"""
        if len(self.short_term.recent_tasks) <= 10:
            return self.get_full_context_for_llm("")
        
        history_text = "\n".join({
            f"{t['task']} → {t['result']}" 
            for t in self.short_term.recent_tasks
        })

        prompt = f"""Summarize this task execution history in 3 concise sentences:
        {history_text}
        Focus on patterns, preferences and recent context."""

        response = await llm.ainvoke(prompt)
        summary = response.content

        sections = []

        #current task progress
        working_ctx = self.working.get_context_summary()
        if working_ctx != "No execution history yet.":
            sections.append(f"## Current Task Progress\n{working_ctx}")
        
        #summarized history instead of full list
        sections.append(f"## Summarized Session History\n{summary}")

        #user preferences 
        longterm_ctx = self.long_term.get_relevant_context("", k=3)
        if longterm_ctx != "No stored preferences found.":
            sections.append(f"## User Preferences\n{longterm_ctx}")

        return "\n\n".join(sections) if sections else "No previous context available."

# --- FACTORY FUNCTION ---
_memory_managers: Dict[str, MemoryManager] = {}  # session_id → manager

def get_memory_manager(user_id: str, session_id: str) -> MemoryManager:
    """Get or create memory manager for session"""
    if session_id not in _memory_managers:
        _memory_managers[session_id] = MemoryManager(user_id, session_id)
    return _memory_managers[session_id]


def clear_session_memory(session_id: str):
    """Called when user says 'start new chat'"""
    if session_id in _memory_managers:
        _memory_managers[session_id].start_new_chat()

