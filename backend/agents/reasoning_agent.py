import os
import asyncio
import logging
import json
from typing import Dict, Any
from dotenv import load_dotenv

# Groq & LangChain Imports
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

# Project Utilities
from agents.utils.protocol import Channels, AgentMessage, MessageType, AgentType
from agents.utils.broker import broker

load_dotenv()
logger = logging.getLogger(__name__)

# --- Configuration ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
REASONING_MODEL = "llama-3.3-70b-versatile"

class ReasoningAgent:
    def __init__(self):
        self.llm = ChatGroq(
            model=REASONING_MODEL,
            temperature=0.2, # Slightly higher than action layer for creativity in summaries
            groq_api_key=GROQ_API_KEY
        )
        
        self.system_prompt = """
            ROLE: You are the REASONING AGENT — the cognitive brain of the AURA multi-agent system.

            PURPOSE:
            You are responsible for all high-level intellectual processing inside AURA.
            You transform raw or intermediate outputs from other agents into meaningful,
            actionable, and human-understandable results.

            CORE RESPONSIBILITIES:
            1. Text Summarization: Condense long or complex content into structured key points.
            2. Information Extraction: Identify and structure specific data (e.g., names, dates, entities, links, values).
            3. Text Generation: Generate coherent, context-aware text based on instructions.
            4. Code Generation: Produce clean, correct code snippets based on requirements.
            5. Code Debugging: Analyze code, detect errors, and suggest precise fixes.
            6. Explanation & Teaching: Explain documents, concepts, or outputs in clear, understandable language.
            7. Decision Support: Recommend next steps based on previous results or failures.
            8. Comparison & Evaluation: Compare outputs, approaches, or datasets logically and objectively.
            9. Validation & Consistency Checking: Detect contradictions, missing elements, or logical flaws.

            STRICT OPERATIONAL RULES:
            - You NEVER interact with UI elements, browsers, mouse, keyboard, or operating system.
            - You NEVER execute tools or external actions.
            - You ONLY reason over the content and parameters provided by the Coordinator or Action Layer.
            - If required data is missing or ambiguous, explicitly state what is needed.
            - You MUST avoid hallucinating unknown information.
            - You MUST return your output as a valid JSON object and nothing else.

            OUTPUT FORMAT:
            {
            "result": <your main output>,
            "metadata": {
                "confidence": <0.0 - 1.0>,
                "notes": <optional>,
                "assumptions": <optional>
            }
            }

            You are an internal reasoning component, not a user-facing assistant.
            Your goal is correctness, clarity, and usefulness to the system.
            """


    async def process_reasoning_task(self, task_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes the logic requested by the Coordinator.
        """
        ai_prompt = task_payload.get("ai_prompt", "Process the following content.")
        content = task_payload.get("content", "") # Data passed from Coordinator
        extra_params = task_payload.get("extra_params", {})

        prompt_template = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("user", "TASK: {ai_prompt}\n\nDATA TO PROCESS:\n{content}\n\nEXTRA PARAMETERS: {params}")
        ])

        chain = prompt_template | self.llm | JsonOutputParser()

        try:
            logger.info(f"🧠 Reasoning Agent processing task: {ai_prompt[:50]}...")
            
            # Call Groq
            response = await chain.ainvoke({
                "ai_prompt": ai_prompt,
                "content": content,
                "params": json.dumps(extra_params)
            })

            return {
                "status": "success",
                "content": response.get("result", str(response)), # The actual logic output
                "metadata": response.get("metadata", {})
            }

        except Exception as e:
            logger.error(f"❌ Reasoning Agent Error: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }

async def start_reasoning_agent():
    agent = ReasoningAgent()
    logger.info(f"✅ Reasoning Agent (Groq) started using {REASONING_MODEL}")

    async def handle_reasoning_request(message: AgentMessage):
        """
        Callback for when the Coordinator sends a task to the Reasoning channel.
        """
        task_id = message.task_id
        payload = message.payload # Contains ai_prompt and content

        # Process the logic
        result = await agent.process_reasoning_task(payload)

        # Send response back to Coordinator
        response_msg = AgentMessage(
            message_type=MessageType.EXECUTION_RESULT,
            sender=AgentType.REASONING,
            receiver=AgentType.COORDINATOR,
            session_id=message.session_id,
            task_id=task_id,
            response_to=message.message_id,
            payload=result
        )

        await broker.publish(Channels.REASONING_TO_COORDINATOR, response_msg)
        logger.info(f"📤 Sent reasoning result for task {task_id}")

    # Subscribe to the reasoning channel
    broker.subscribe(Channels.COORDINATOR_TO_REASONING, handle_reasoning_request)

    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(start_reasoning_agent())