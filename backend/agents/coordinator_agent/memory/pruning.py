"""
Background task for memory pruning
"""

import asyncio
from datetime import datetime, timedelta
from memory_store import get_memory_manager, _memory_managers

async def prune_long_term_memory_task():
    """Background task to prune old vector store entries"""
    print("pruning task started")
    while True:
        await asyncio.sleep(86400)  # Run daily
        
        for session_id, mgr in _memory_managers.items():
            try:
                mgr.long_term.prune_old_entries(days=90)
                print(f"✅ Pruned long-term memory for session {session_id}")
            except Exception as e:
                print(f"❌ Pruning failed for {session_id}: {e}")

# Start background task
asyncio.create_task(prune_long_term_memory_task())