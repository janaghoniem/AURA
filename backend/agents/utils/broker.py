from typing import Dict, List, Callable
from agents.utils.protocol import AgentMessage

class MessageBroker:
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}
        self._running = False # Add a running state

    async def start(self):
        """Initializes the broker (e.g., connects to Redis, starts threads)."""
        # For this in-memory broker, simply set the running state.
        self._running = True
        print("MessageBroker started.") 

    async def stop(self):
        """Cleans up broker resources (e.g., closes connections)."""
        # For this in-memory broker, simply set the running state.
        self._running = False
        print("MessageBroker stopped.")
        
    # Helper property for health check in server.py
    @property
    def running(self):
        return self._running

    def subscribe(self, topic: str, callback: Callable):
        if topic not in self.subscribers:
            self.subscribers[topic] = []
        self.subscribers[topic].append(callback)

    async def publish(self, topic: str, message: AgentMessage):
        if topic in self.subscribers:
            for callback in self.subscribers[topic]:
                await callback(message)

broker = MessageBroker()