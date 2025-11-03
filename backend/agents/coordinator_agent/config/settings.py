"""
Configuration settings for Coordinator Agent
Centralizes all service URLs and environment variables
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Service URLs - Update these based on your deployment
EXECUTION_AGENT_URL = os.getenv("EXECUTION_AGENT_URL", "http://127.0.0.1:8001/execute")
REASONING_AGENT_URL = os.getenv("REASONING_AGENT_URL", "http://127.0.0.1:8002/reason")
RL_FEEDBACK_URL = os.getenv("RL_FEEDBACK_URL", "http://127.0.0.1:8003/feedback")
LANGUAGE_AGENT_URL = os.getenv("LANGUAGE_AGENT_URL", "http://127.0.0.1:8004/process")

# LLM Configuration
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.5-flash")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Server Configuration
COORDINATOR_HOST = os.getenv("COORDINATOR_HOST", "0.0.0.0")
COORDINATOR_PORT = int(os.getenv("COORDINATOR_PORT", 8000))

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")