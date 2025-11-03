import os
from dotenv import load_dotenv

load_dotenv()

EXECUTION_AGENT_URL = os.getenv("EXECUTION_AGENT_URL", "http://localhost:8001/execute")
REASONING_AGENT_URL = os.getenv("REASONING_AGENT_URL", "http://localhost:8002/reason")
RL_FEEDBACK_URL = os.getenv("RL_FEEDBACK_URL", "http://localhost:8003/feedback")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3")
