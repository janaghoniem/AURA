"""
Complete ReAct Loop for ANY Mobile Task
Works dynamically for any app, any screen, any goal

Flow:
1. Get current UI tree from Android
2. LLM analyzes UI tree + goal → generates JSON action
3. Send action to Android for execution
4. Android executes primitive (click/type/scroll/etc)
5. Android sends back new UI tree
6. Loop until goal achieved or max steps
"""

import logging
import asyncio
import json
import re
import httpx
from typing import Optional, List, Dict, Any
from agents.utils.device_protocol import (
    MobileTaskRequest, MobileTaskResult, UIAction, ActionResult,
    SemanticUITree
)

logger = logging.getLogger(__name__)


class MobileReActStrategy:
    """
    Generic ReAct loop that works for ANY mobile automation task
    Uses LLM to understand UI and generate actions dynamically
    """
    
    def __init__(self, device_id: str = "default_device"):
        self.device_id = device_id
        self.backend_url = "http://localhost:8000"
        
        # Initialize Groq LLM
        from groq import AsyncGroq
        import os
        self.llm_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = "llama-3.3-70b-versatile"
        
        # Device state cache
        self.current_ui_tree: Optional[SemanticUITree] = None
        
        logger.info(f"✅ Initialized MobileReActStrategy for device {device_id}")
    
    async def execute_task(self, task: MobileTaskRequest) -> MobileTaskResult:
        """
        Execute ANY task using ReAct loop
        
        Args:
            task: Task request with natural language goal
            
        Returns:
            Execution result
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"🎯 STARTING REACT LOOP")
        logger.info(f"{'='*70}")
        logger.info(f"Goal: {task.ai_prompt}")
        logger.info(f"Device: {task.device_id}")
        logger.info(f"Max Steps: {task.max_steps}")
        logger.info(f"Timeout: {task.timeout_seconds}s")
        logger.info(f"{'='*70}\n")
        
        start_time = asyncio.get_event_loop().time()
        actions_executed: List[UIAction] = []
        thought_history: List[str] = []
        
        # Get initial UI state
        logger.info(f"👁️ Getting initial UI state...")
        ui_tree = await self._fetch_ui_tree_from_device()
        
        if not ui_tree:
            return MobileTaskResult(
                task_id=task.task_id,
                status="failed",
                steps_taken=0,
                actions_executed=[],
                execution_time_ms=0,
                error="Failed to get initial UI tree from device"
            )
        
        self.current_ui_tree = ui_tree
        logger.info(f"✅ Initial UI captured: {ui_tree.screen_name or ui_tree.app_name}")
        logger.info(f"   Elements found: {len(ui_tree.elements)}")
        
        # ReAct Loop
        for step in range(task.max_steps):
            logger.info(f"\n{'='*70}")
            logger.info(f"📍 STEP {step + 1}/{task.max_steps}")
            logger.info(f"{'='*70}")
            
            # Check timeout
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > task.timeout_seconds:
                logger.warning(f"⏱️ Timeout reached")
                return self._build_result(
                    task_id=task.task_id,
                    status="timeout",
                    steps=step,
                    actions=actions_executed,
                    elapsed=elapsed,
                    error=f"Timeout after {task.timeout_seconds}s"
                )
            
            # ================================================================
            # THINK: Analyze current UI and decide next action
            # ================================================================
            logger.info(f"🤔 THINK: Analyzing current screen...")
            
            observation = self.current_ui_tree.to_semantic_string()
            logger.info(f"📋 Current Observation:\n{observation}\n")
            
            thought, action_json = await self._think_and_decide(
                goal=task.ai_prompt,
                observation=observation,
                thought_history=thought_history,
                step_number=step + 1
            )
            
            if not action_json:
                logger.error(f"❌ Failed to generate valid action")
                return self._build_result(
                    task_id=task.task_id,
                    status="failed",
                    steps=step,
                    actions=actions_executed,
                    elapsed=elapsed,
                    error="LLM failed to generate valid action"
                )
            
            thought_history.append(thought)
            logger.info(f"💭 Thought: {thought}")
            
            # Check if goal achieved
            if action_json.get("action_type") == "complete":
                logger.info(f"\n{'='*70}")
                logger.info(f"✅ GOAL ACHIEVED!")
                logger.info(f"{'='*70}")
                logger.info(f"Reason: {action_json.get('reason', 'Task completed')}")
                
                return self._build_result(
                    task_id=task.task_id,
                    status="success",
                    steps=step + 1,
                    actions=actions_executed,
                    elapsed=elapsed,
                    completion_reason=action_json.get("reason", "Task completed")
                )
            
            # ================================================================
            # ACT: Execute the decided action on Android device
            # ================================================================
            logger.info(f"🎬 ACT: Executing action...")
            logger.info(f"   Type: {action_json.get('action_type')}")
            
            action = self._json_to_ui_action(action_json)
            logger.info(f"   Action: {action.dict()}")
            
            result = await self._execute_action_on_device(action)
            actions_executed.append(action)
            
            if not result.success:
                logger.warning(f"⚠️ Action execution failed: {result.error}")
                # Continue - LLM might adapt
            else:
                logger.info(f"✅ Action executed successfully")
            
            # ================================================================
            # OBSERVE: Get new UI state after action
            # ================================================================
            logger.info(f"👁️ OBSERVE: Getting new UI state...")
            
            # Wait for UI to update
            await asyncio.sleep(0.5)
            
            new_ui_tree = await self._fetch_ui_tree_from_device()
            
            if new_ui_tree:
                self.current_ui_tree = new_ui_tree
                logger.info(f"✅ New UI captured: {new_ui_tree.screen_name or new_ui_tree.app_name}")
                logger.info(f"   Elements: {len(new_ui_tree.elements)}")
            else:
                logger.warning(f"⚠️ Failed to get new UI tree, using previous")
        
        # Max steps reached without completion
        logger.warning(f"\n{'='*70}")
        logger.warning(f"⚠️ MAX STEPS REACHED WITHOUT COMPLETION")
        logger.warning(f"{'='*70}")
        
        return self._build_result(
            task_id=task.task_id,
            status="failed",
            steps=task.max_steps,
            actions=actions_executed,
            elapsed=asyncio.get_event_loop().time() - start_time,
            error=f"Max steps ({task.max_steps}) reached"
        )
    
    async def _think_and_decide(
        self,
        goal: str,
        observation: str,
        thought_history: List[str],
        step_number: int
    ) -> tuple[str, Optional[Dict]]:
        """
        Use LLM to analyze UI and decide next action
        
        Returns:
            (thought, action_json) tuple
        """
        # Build context from previous thoughts
        history_context = ""
        if thought_history:
            history_context = "Previous thoughts:\n" + "\n".join(
                f"{i+1}. {t}" for i, t in enumerate(thought_history[-3:])
            )
        
        prompt = f"""You are a mobile automation agent. You can see the current screen and must decide the next action.

GOAL: {goal}

CURRENT SCREEN:
{observation}

{history_context}

Analyze the screen and decide what to do next. Think step-by-step:
1. What is currently visible on screen?
2. Is the goal already achieved? If yes, output {{"action_type": "complete", "reason": "..."}}
3. If not, what is the NEXT SINGLE action needed to progress toward the goal?

AVAILABLE ACTIONS:
- click: Click an element by its element_id
- type: Type text into a text field
- scroll: Scroll the screen (up/down/left/right)
- wait: Wait for UI to update (in milliseconds)
- global_action: System actions (HOME, BACK, RECENTS)
- complete: Mark task as done

OUTPUT FORMAT (JSON only, no other text):
{{
  "thought": "Brief explanation of reasoning",
  "action_type": "click|type|scroll|wait|global_action|complete",
  "element_id": 5,  // for click/type
  "text": "hello",  // for type
  "direction": "up",  // for scroll
  "duration": 1000,  // for wait
  "global_action": "HOME",  // for global_action
  "reason": "Why goal is achieved"  // for complete
}}

RESPOND WITH VALID JSON ONLY:"""
        
        try:
            response = await self.llm_client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a mobile automation expert. Always respond with ONLY valid JSON, no markdown, no extra text."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.2,
                max_tokens=500
            )
            
            response_text = response.choices[0].message.content.strip()
            logger.debug(f"🤖 Raw LLM response:\n{response_text}")
            
            # Extract JSON
            json_str = self._extract_json_from_response(response_text)
            
            if not json_str:
                logger.error(f"❌ No JSON found in LLM response")
                return ("Failed to parse response", None)
            
            action_json = json.loads(json_str)
            thought = action_json.get("thought", "No thought provided")
            
            return (thought, action_json)
        
        except Exception as e:
            logger.error(f"❌ LLM error: {e}", exc_info=True)
            return (f"Error: {e}", None)
    
    def _extract_json_from_response(self, text: str) -> Optional[str]:
        """Extract JSON from LLM response, handling various formats"""
        # Remove markdown code blocks
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        
        # Find JSON object
        match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
        if match:
            return match.group(0).strip()
        
        return None
    
    def _json_to_ui_action(self, action_json: Dict) -> UIAction:
        """Convert JSON decision to UIAction"""
        return UIAction(
            action_type=action_json.get("action_type"),
            element_id=action_json.get("element_id"),
            text=action_json.get("text"),
            direction=action_json.get("direction"),
            duration=action_json.get("duration", 1000),
            global_action=action_json.get("global_action")
        )
    
    async def _fetch_ui_tree_from_device(self) -> Optional[SemanticUITree]:
        """
        Fetch current UI tree from Android device
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.backend_url}/device/{self.device_id}/ui-tree",
                    timeout=5.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return SemanticUITree(**data)
                else:
                    logger.error(f"❌ Failed to fetch UI tree: HTTP {response.status_code}")
                    return None
        
        except Exception as e:
            logger.error(f"❌ Error fetching UI tree: {e}")
            return None
    
    async def _execute_action_on_device(self, action: UIAction) -> ActionResult:
        """
        Send action to Android device for execution
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.backend_url}/device/{self.device_id}/execute-action",
                    json=action.dict(),
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return ActionResult(**data)
                else:
                    logger.error(f"❌ Action execution failed: HTTP {response.status_code}")
                    return ActionResult(
                        action_id=action.action_id,
                        success=False,
                        error=f"HTTP {response.status_code}",
                        execution_time_ms=0
                    )
        
        except Exception as e:
            logger.error(f"❌ Error executing action: {e}")
            return ActionResult(
                action_id=action.action_id,
                success=False,
                error=str(e),
                execution_time_ms=0
            )
    
    def _build_result(
        self,
        task_id: str,
        status: str,
        steps: int,
        actions: List[UIAction],
        elapsed: float,
        error: Optional[str] = None,
        completion_reason: Optional[str] = None
    ) -> MobileTaskResult:
        """Build task result"""
        return MobileTaskResult(
            task_id=task_id,
            status=status,
            steps_taken=steps,
            actions_executed=actions,
            execution_time_ms=int(elapsed * 1000),
            error=error,
            completion_reason=completion_reason
        )


async def execute_mobile_task(task: MobileTaskRequest) -> MobileTaskResult:
    """
    Main entry point for executing mobile automation tasks
    Works with ANY task dynamically - no hardcoding needed
    """
    strategy = MobileReActStrategy(device_id=task.device_id)
    return await strategy.execute_task(task)
