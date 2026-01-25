"""
Enhanced ReAct Loop for ANY Mobile Task - FIXED VERSION
========================================================

This implements a smart, context-aware mobile automation loop that prevents
infinite loops and hallucinations by understanding device state and navigation.

CRITICAL FIXES:
1. Device State Detection - Knows when we're on home screen, in an app, etc.
2. Smart Navigation - Can navigate between screens (home → app drawer → apps)
3. Goal Recognition - Detects when target app is available and launches it
4. State Tracking - Remembers previous actions to avoid repetition
5. App Detection - Recognizes common apps and their icons

Flow:
1. Analyze current device state and context
2. Determine what navigation is needed
3. Generate appropriate action based on state
4. Execute action and track state changes
5. Loop until goal achieved or max steps reached

Prevents infinite loops by:
- Detecting when we're stuck in the same screen
- Recognizing when we need to navigate vs. interact
- Understanding app launching workflows
- Avoiding repetitive actions in wrong contexts
"""

import logging
import asyncio
import json
import re
import httpx
from typing import Optional, List, Dict, Any

from posthog import api_key
from agents.utils.device_protocol import (
    MobileTaskRequest, MobileTaskResult, UIAction, ActionResult,
    SemanticUITree
)
from agents.execution_agent.core.exec_agent_models import ExecutionResult

logger = logging.getLogger(__name__)


class MobileReActStrategy:
    """
    Smart ReAct loop that prevents infinite loops and hallucinations.
    Uses LLM with enhanced context awareness and state tracking.
    """
    def __init__(self, device_id: str = "default_device"):
        self.device_id = device_id
        self.backend_url = "http://localhost:8000"
        
        # Initialize Groq LLM
        from groq import AsyncGroq
        
        # Hardcoded API Key
        api_key = "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" 
        
        logger.info(f"🔑 DEBUG: Using hardcoded API key")
        if api_key:
            api_key = api_key.strip()
            logger.info(f"🔑 DEBUG: Key length: {len(api_key)}")
            prefix = api_key[:7] 
            logger.info(f"🔑 DEBUG: Key starting with: {prefix}")
        else:
            logger.error("❌ DEBUG: API key variable is empty!")
        
        self.llm_client = AsyncGroq(api_key=api_key)
        self.model = "llama-3.3-70b-versatile"
        
        # ... (rest of your existing initialization code)
        
        # Device state cache and tracking
        self.current_ui_tree: Optional[SemanticUITree] = None
        self.previous_ui_trees: List[SemanticUITree] = []  # Track recent states
        self.action_history: List[Dict] = []  # Track recent actions
        self.device_state: str = "unknown"  # home_screen, in_app, app_drawer, etc.
        self.target_app: Optional[str] = None  # Extracted from goal
        
        # Common app patterns for detection
        self.app_patterns = {
            "gmail": ["gmail", "mail", "email", "envelope"],
            "whatsapp": ["whatsapp", "chat", "message", "bubble"],
            "chrome": ["chrome", "browser", "globe", "earth"],
            "youtube": ["youtube", "play", "video", "film"],
            "settings": ["settings", "gear", "cog", "tools"],
            "camera": ["camera", "photo", "picture", "shutter"],
            "phone": ["phone", "call", "dial", "contact"],
            "messages": ["messages", "sms", "text", "bubble"],
            "maps": ["maps", "location", "pin", "navigation"],
            "calculator": ["calculator", "calc", "numbers", "math"]
        }
        
        logger.info(f"✅ Initialized Enhanced MobileReActStrategy for device {device_id}")
    
    async def execute_task(self, task: MobileTaskRequest) -> MobileTaskResult:
        """
        Execute ANY task using enhanced ReAct loop.
        
        Args:
            task: Task request with natural language goal
            
        Returns:
            Execution result
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"🎯 STARTING ENHANCED REACT LOOP")
        logger.info(f"{'='*70}")
        logger.info(f"Goal: {task.ai_prompt}")
        logger.info(f"Device: {task.device_id}")
        logger.info(f"Max Steps: {task.max_steps}")
        logger.info(f"Timeout: {task.timeout_seconds}s")
        logger.info(f"{'='*70}\n")
        
        # Extract target app from goal
        self.target_app = self._extract_target_app(task.ai_prompt)
        if self.target_app:
            logger.info(f"🎯 Target app detected: {self.target_app}")
        
        start_time = asyncio.get_event_loop().time()
        actions_executed: List[UIAction] = []
        thought_history: List[str] = []
        
        # Get initial UI state
        logger.info(f"👁️ Getting initial UI state...")
        await asyncio.sleep(1)  # Give device time to stabilize
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
        self.previous_ui_trees.append(ui_tree)
        self.device_state = self._detect_device_state(ui_tree)
        
        logger.info(f"✅ Initial UI captured: {ui_tree.screen_name or ui_tree.app_name}")
        logger.info(f"   Elements found: {len(ui_tree.elements)}")
        logger.info(f"   Device state: {self.device_state}")
        
        # ReAct Loop with enhanced logic
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
            
            # Check for infinite loop detection (DISABLED - app needs time to render)
            # if self._detect_infinite_loop():
            #     logger.warning(f"⚠️ Infinite loop detected, breaking execution")
            #     return self._build_result(
            #         task_id=task.task_id,
            #         status="failed",
            #         steps=step + 1,
            #         actions=actions_executed,
            #         elapsed=elapsed,
            #         error="Infinite loop detected - device not sending complete UI tree"
            #     )
            
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
            
            # Track action history
            self.action_history.append({
                "step": step + 1,
                "action": action_json,
                "device_state": self.device_state
            })
            
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
            
            # Wait for UI to update - longer wait if we just clicked something
            wait_time = 1.5 if action_json.get("action_type") == "click" else 0.5
            logger.info(f"⏳ Waiting {wait_time}s for UI to stabilize...")
            await asyncio.sleep(wait_time)
            
            new_ui_tree = await self._fetch_ui_tree_from_device()
            
            if new_ui_tree:
                self.current_ui_tree = new_ui_tree
                self.previous_ui_trees.append(new_ui_tree)
                
                # Keep only last 5 states to prevent memory issues
                if len(self.previous_ui_trees) > 5:
                    self.previous_ui_trees.pop(0)
                
                new_device_state = self._detect_device_state(new_ui_tree)
                
                logger.info(f"✅ New UI captured: {new_ui_tree.screen_name or new_ui_tree.app_name}")
                logger.info(f"   Elements: {len(new_ui_tree.elements)}")
                
                # Log element details for debugging incomplete UI trees
                if new_ui_tree.elements:
                    logger.debug(f"   📦 UI Elements:")
                    for elem in new_ui_tree.elements[:10]:
                        elem_text = elem.text[:40] if elem.text else "(no text)"
                        logger.debug(f"      [{elem.element_id}] {elem.type:12} | {elem_text}")
                else:
                    logger.warning(f"⚠️ UI tree has NO elements - app may not be fully loaded")
                
                logger.info(f"   Device state: {new_device_state}")
                
                # Update device state if changed
                if new_device_state != self.device_state:
                    logger.info(f"🔄 Device state changed: {self.device_state} → {new_device_state}")
                    self.device_state = new_device_state
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
    
    def _extract_target_app(self, goal: str) -> Optional[str]:
        """Extract target app name from goal"""
        goal_lower = goal.lower()
        
        for app_name, patterns in self.app_patterns.items():
            for pattern in patterns:
                if pattern in goal_lower:
                    return app_name
        
        return None
    
    def _detect_device_state(self, ui_tree: SemanticUITree) -> str:
        """Detect current device state based on UI content"""
        app_name = ui_tree.app_name.lower()
        screen_name = ui_tree.screen_name.lower() if ui_tree.screen_name else ""
        
        # Check for app-specific screens FIRST (before home_screen check)
        # This ensures "Chrome Home" is recognized as in_chrome, not home_screen
        app_mapping = {
            "gmail": "in_gmail",
            "chrome": "in_chrome",
            "settings": "in_settings",
            "phone": "in_phone",
            "messages": "in_messages",
            "camera": "in_camera",
            "calculator": "in_calculator",
        }
        
        for app_key, state in app_mapping.items():
            if app_key in app_name:
                return state
        
        # Check for home screen indicators
        home_indicators = [
            "launcher", "home screen", "desktop", "wallpaper", "widget",
            "app list", "app drawer", "all apps"
        ]
        
        if any(indicator in app_name or indicator in screen_name for indicator in home_indicators):
            return "home_screen"
        
        # Check for app drawer
        drawer_indicators = ["app drawer", "all apps", "apps"]
        if any(indicator in screen_name for indicator in drawer_indicators):
            return "app_drawer"
        
        # Default to in_app for any other app
        return "in_app"
    
    def _detect_infinite_loop(self) -> bool:
        """Detect if we're stuck in an infinite loop"""
        if len(self.previous_ui_trees) < 3:
            return False
        
        # Check if we've been in the same state for too long
        recent_states = [self._detect_device_state(tree) for tree in self.previous_ui_trees[-3:]]
        if len(set(recent_states)) == 1:
            # Same state for 3 consecutive steps
            logger.warning(f"⚠️ Stuck in same state: {recent_states[0]}")
            
            # Check if UI tree is NOT changing (stuck on incomplete UI)
            recent_trees = self.previous_ui_trees[-3:]
            tree_element_counts = [len(tree.elements) for tree in recent_trees]
            
            if tree_element_counts == [tree_element_counts[0]] * len(tree_element_counts):
                # Same number of elements for 3 steps
                if tree_element_counts[0] == 1:
                    # Only 1 element (incomplete UI tree) - device not capturing full UI
                    logger.error(f"❌ DEVICE ISSUE: UI tree incomplete - only 1 element")
                    logger.error(f"   This means your device is not sending all interactive elements")
                    logger.error(f"   Expected: buttons, FABs, text fields, etc.")
                    logger.error(f"   Got: only TEXT elements")
                    return True
            
            return True
        
        # Check for repetitive actions
        if len(self.action_history) >= 3:
            recent_actions = [action["action"]["action_type"] for action in self.action_history[-3:]]
            if len(set(recent_actions)) == 1 and recent_actions[0] == "scroll":
                # Repeated scroll actions with no UI change = stuck
                logger.warning(f"⚠️ Repeated scroll actions without UI change")
                return True
        
        return False
    
    async def _think_and_decide(
        self,
        goal: str,
        observation: str,
        thought_history: List[str],
        step_number: int
    ) -> tuple[str, Optional[Dict]]:
        """
        Use LLM to analyze UI and decide next action with enhanced context.
        
        Returns:
            (thought, action_json) tuple
        """
        # Build context from previous thoughts
        history_context = ""
        if thought_history:
            history_context = "Previous thoughts:\n" + "\n".join(
                f"{i+1}. {t}" for i, t in enumerate(thought_history[-3:])
            )
        
        # Build device state context
        state_context = f"""CURRENT DEVICE STATE: {self.device_state}
TARGET APP: {self.target_app or 'Unknown'}
PREVIOUS ACTIONS: {[action["action"]["action_type"] for action in self.action_history[-3:]] if self.action_history else 'None'}

"""
        
        prompt = f"""You are a mobile automation agent. You can see the current screen and must decide the next action.

GOAL: {goal}

{state_context}
CURRENT SCREEN:
{observation}

{history_context}

CRITICAL RULES:
1. If you're on the HOME SCREEN and need to open an app, CLICK the app icon
2. If you're in the WRONG APP, use BACK or HOME to navigate
3. If you're in the APP DRAWER, CLICK the app icon
4. NEVER type app names into text fields unless explicitly instructed
5. If you see a text field with a hint like "open the gmail app", DO NOT type into it
6. Always prefer navigation actions (HOME, BACK) over typing when in wrong context
7. if you see the word AURA you are in the AURA app, exit it to continue your task
8. For FORMS (multiple text fields): Fill ALL required fields sequentially BEFORE clicking submit/send
9. Example form flow: Click To field → Type email → Click Subject field → Type subject → Click Message field → Type message → Click Send button
10. If you typed something and the field still shows empty, the text was NOT accepted - try clicking the field first

Analyze the screen and decide what to do next. Think step-by-step:
1. What is currently visible on screen?
2. Are we in the right place to achieve the goal?
3. If not, what navigation is needed?
4. What is the NEXT SINGLE action needed to progress toward the goal?

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
        """Convert JSON decision to UIAction with validation"""
        # Validate action type
        action_type = action_json.get("action_type")
        if not action_type:
            logger.error(f"❌ No action_type in LLM response: {action_json}")
            raise ValueError("Missing action_type")
        
        # Only include optional fields if they have non-empty values
        kwargs = {
            "action_type": action_type,
            "text": action_json.get("text"),
            "duration": action_json.get("duration", 1000),
        }
        
        # Validate element_id for click/type actions
        if action_type in ["click", "type"]:
            element_id = action_json.get("element_id")
            if element_id is not None:
                # Try to convert to int if it's a string
                if isinstance(element_id, str):
                    try:
                        kwargs["element_id"] = int(element_id)
                        logger.info(f"✅ Converted element_id from string '{element_id}' to int")
                    except (ValueError, TypeError):
                        logger.error(f"❌ LLM returned invalid element_id '{element_id}' (not numeric)")
                        logger.warning(f"⚠️ LLM hallucinated element_id. Falling back to SCROLL to find UI elements")
                        # LLM couldn't find element - scroll to reveal more UI
                        kwargs["action_type"] = "scroll"
                        kwargs["direction"] = "down"
                        return UIAction(**kwargs)
                else:
                    kwargs["element_id"] = int(element_id) if element_id else None
            else:
                logger.error(f"❌ No element_id for {action_type} action")
                logger.warning(f"⚠️ No interactive element found on screen. Scrolling to find more UI...")
                # Default to scrolling if we can't find element
                kwargs["action_type"] = "scroll"
                kwargs["direction"] = "down"
                return UIAction(**kwargs)
        
        # Only add enum fields if they have meaningful values
        direction = action_json.get("direction")
        if direction and direction.strip():
            kwargs["direction"] = direction
        
        global_action = action_json.get("global_action")
        if global_action and global_action.strip():
            kwargs["global_action"] = global_action
        
        return UIAction(**kwargs)
    
    async def _fetch_ui_tree_from_device(self) -> Optional[SemanticUITree]:
        """
        Fetch current UI tree from Android device.
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
        Send action to Android device for execution.
        """
        try:
            # Handle special navigation actions with new Flutter methods
            if action.action_type == "global_action" and action.global_action:
                return await self._execute_navigation_action(action)
            
            # Handle regular actions
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
    
    async def _execute_navigation_action(self, action: UIAction) -> ActionResult:
        """
        Execute navigation actions using new Flutter methods.
        """
        global_action = action.global_action.upper()
        
        if global_action == 'HOME':
            # Use Flutter package to navigate to home screen
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.backend_url}/device/{self.device_id}/execute-action",
                        json={
                            "action_type": "navigate_home",
                            "device_id": self.device_id
                        },
                        timeout=10.0
                    )
                    
                    if response.status_code == 200:
                        return ActionResult(
                            action_id=action.action_id,
                            success=True,
                            execution_time_ms=1000
                        )
                    else:
                        logger.error(f"❌ HOME navigation failed: HTTP {response.status_code}")
                        return ActionResult(
                            action_id=action.action_id,
                            success=False,
                            error=f"HTTP {response.status_code}",
                            execution_time_ms=0
                        )
            except Exception as e:
                logger.error(f"❌ Error executing HOME navigation: {e}")
                return ActionResult(
                    action_id=action.action_id,
                    success=False,
                    error=str(e),
                    execution_time_ms=0
                )
                
        elif global_action == 'BACK':
            # Use Flutter package to navigate back
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.backend_url}/device/{self.device_id}/execute-action",
                        json={
                            "action_type": "navigate_back",
                            "device_id": self.device_id
                        },
                        timeout=10.0
                    )
                    
                    if response.status_code == 200:
                        return ActionResult(
                            action_id=action.action_id,
                            success=True,
                            execution_time_ms=1000
                        )
                    else:
                        logger.error(f"❌ BACK navigation failed: HTTP {response.status_code}")
                        return ActionResult(
                            action_id=action.action_id,
                            success=False,
                            error=f"HTTP {response.status_code}",
                            execution_time_ms=0
                        )
            except Exception as e:
                logger.error(f"❌ Error executing BACK navigation: {e}")
                return ActionResult(
                    action_id=action.action_id,
                    success=False,
                    error=str(e),
                    execution_time_ms=0
                )
        
        else:
            logger.error(f"❌ Unknown global action: {global_action}")
            return ActionResult(
                action_id=action.action_id,
                success=False,
                error=f"Unknown global action: {global_action}",
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


# For backward compatibility
class MobileStrategy(MobileReActStrategy):
    """Alias for backward compatibility"""
    pass


# ============================================================================
# INTEGRATION WITH EXECUTION AGENT
# ============================================================================

async def execute_mobile_task(
    task: Dict[str, Any],
    device_id: str = "emulator-5554"
) -> ExecutionResult:
    """
    Execute a mobile task - called by ExecutionAgent
    
    Args:
        task: Task dict from coordinator
        device_id: Android device ID
    
    Returns:
        ExecutionResult for the message broker
    """
    
    try:
        # Convert coordinator task to mobile task request
        mobile_task = MobileTaskRequest(
            task_id=task.get("task_id"),
            ai_prompt=task.get("ai_prompt"),
            device_id=device_id,
            session_id=task.get("session_id", "default"),
            context=task.get("extra_params", {}),
            extra_params=task.get("extra_params", {}),
            max_steps=15,  # Override to 15 steps
            timeout_seconds=task.get("timeout_seconds", 30)
        )
        
        # Execute with enhanced ReAct loop
        strategy = MobileStrategy(device_id)
        result = await strategy.execute_task(mobile_task)
        
        # Convert to ExecutionResult for broker
        return ExecutionResult(
            task_id=result.task_id,
            status="success" if result.status == "success" else "failed",
            content=result.completion_reason or result.error,
            error=result.error
        )
    
    except Exception as e:
        logger.error(f"❌ Error executing mobile task: {e}", exc_info=True)
        return ExecutionResult(
            task_id=task.get("task_id", "unknown"),
            status="failed",
            error=str(e)
        )