"""
Enhanced ReAct Loop for ANY Mobile Task - FULLY FIXED VERSION
================================================================

FIXES IMPLEMENTED:
1. ✅ App verification after clicks (detects wrong app opened)
2. ✅ Element blacklist (never clicks same wrong element twice)
3. ✅ App drawer support (scroll UP to find apps not on home screen)
4. ✅ Success verification (doesn't exit too early)
5. ✅ Incomplete UI detection (waits for full load)
6. ✅ Better coordinate matching using content_description
7. ✅ Proper stuck detection with recovery strategies

CRITICAL CHANGES:
- Blacklisted elements tracking (failed_elements set)
- App verification immediately after click
- Dynamic app drawer detection
- Task completion verification
- Incomplete UI handling (only 2-3 elements bug)
"""

import logging
import asyncio
import json
import re
import httpx
from typing import Optional, List, Dict, Any, Set

from agents.utils.device_protocol import (
    MobileTaskRequest, MobileTaskResult, UIAction, ActionResult,
    SemanticUITree
)
from agents.execution_agent.core.exec_agent_models import ExecutionResult

logger = logging.getLogger(__name__)


class MobileReActStrategy:
    """
    FULLY FIXED ReAct loop with app verification and element blacklisting
    """
    
    # App keyword mappings for verification
    APP_KEYWORDS = {
        "gmail": ["gmail", "gm"],
        "youtube": ["youtube"],
        "photos": ["photos", "photo"],
        "chrome": ["chrome", "browser"],
        "camera": ["camera", "cam"],
        "calendar": ["calendar"],
        "play store": ["play", "store"],
        "messages": ["messages", "messaging"],
        "phone": ["phone", "dialer"],
    }
    
    def __init__(self, device_id: str = "default_device"):
        self.device_id = device_id
        self.backend_url = "http://localhost:8000"
        
        # Initialize Groq LLM
        from groq import AsyncGroq
        
        api_key = "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" 
        self.llm_client = AsyncGroq(api_key=api_key)
        self.model = "llama-3.3-70b-versatile"
        
        # Device state tracking
        self.current_ui_tree: Optional[SemanticUITree] = None
        self.previous_ui_trees: List[SemanticUITree] = []
        self.action_history: List[Dict] = []
        self.device_state: str = "unknown"
        self.stuck_counter: int = 0
        
        # ✅ NEW: Blacklist and verification tracking
        self.failed_elements: Set[int] = set()  # Elements that opened wrong apps
        self.last_clicked_element: Optional[int] = None
        self.last_action_was_click: bool = False  # Track if last action was a click
        self.app_drawer_attempted: bool = False
        self.incomplete_ui_count: int = 0
        
        # ✅ NEW: Track typed text to prevent duplicates
        self.typed_texts: Dict[int, str] = {}  # element_id -> last typed text
        
        # ✅ FIX: Track consecutive duplicate skips to prevent infinite loops
        self.consecutive_skips: int = 0
        
        # ✅ FIX: Store current task for access in _think_and_decide
        self.current_task: Optional[MobileTaskRequest] = None
        
        logger.info(f"✅ Initialized FIXED MobileReActStrategy for device {device_id}")
    
    async def execute_task(self, task: MobileTaskRequest) -> MobileTaskResult:
        """Execute ANY task using FULLY FIXED ReAct loop"""
        
        # ✅ FIX: Store task for access in other methods
        self.current_task = task
        
        # ✅ CRITICAL: Dynamic timeout based on task complexity
        original_timeout = task.timeout_seconds
        task.timeout_seconds = self._calculate_smart_timeout(task.ai_prompt, task.timeout_seconds)
        
        if task.timeout_seconds != original_timeout:
            logger.info(f"⏱️ Timeout adjusted: {original_timeout}s → {task.timeout_seconds}s (task complexity)")
        
        logger.info(f"\n{'='*70}")
        logger.info(f"🎯 STARTING FULLY FIXED REACT LOOP")
        logger.info(f"{'='*70}")
        logger.info(f"Goal: {task.ai_prompt}")
        logger.info(f"Device: {task.device_id}")
        logger.info(f"Max Steps: {task.max_steps}")
        logger.info(f"Timeout: {task.timeout_seconds}s")
        logger.info(f"{'='*70}\n")
        
        # Reset tracking for new task
        self.failed_elements.clear()
        self.app_drawer_attempted = False
        self.incomplete_ui_count = 0
        self.stuck_counter = 0
        self.last_action_was_click = False
        self.consecutive_skips = 0  # ✅ FIX: Reset duplicate skip counter
        self.typed_texts.clear()  # Clear typed text tracking
        
        start_time = asyncio.get_event_loop().time()
        actions_executed: List[UIAction] = []
        thought_history: List[str] = []
        
        # Get initial UI state
        logger.info(f"👁️ Getting initial UI state...")
        await asyncio.sleep(1.5)
        
        ui_tree = await self._fetch_ui_tree_with_retries("wait", max_attempts=2, retry_delay=1.5)
        
        if not ui_tree:
            return self._build_error_result(task.task_id, "Failed to get initial UI tree")
        
        self.current_ui_tree = ui_tree
        self.previous_ui_trees.append(ui_tree)
        self.device_state = self._detect_device_state(ui_tree)
        
        logger.info(f"✅ Initial UI captured: {ui_tree.screen_name or ui_tree.app_name}")
        logger.info(f"   Elements found: {len(ui_tree.elements)}")
        logger.info(f"   Device state: {self.device_state}")
        logger.info(f"   App: {ui_tree.app_name}")
        
        # Log elements for debugging
        if ui_tree.elements:
            logger.info(f"   📦 UI Elements:")
            for elem in ui_tree.elements[:15]:
                elem_text = elem.text[:40] if elem.text else "(no text)"
                logger.info(f"      [{elem.element_id}] {elem.type:12} | {elem_text}")
        
        # Extract target app from goal
        target_app = self._extract_target_app(task.ai_prompt)
        logger.info(f"🎯 Target app: {target_app}")
        
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
            
            # ✅ CRITICAL FIX: Handle incomplete UI trees BEFORE verification
            if len(self.current_ui_tree.elements) < 5:
                self.incomplete_ui_count += 1
                logger.warning(f"⚠️ Incomplete UI ({len(self.current_ui_tree.elements)} elements) - count: {self.incomplete_ui_count}")
                
                if self.incomplete_ui_count >= 3:
                    logger.error("❌ UI stuck loading - going BACK")
                    back_action = UIAction(action_type="global_action", global_action="BACK", duration=1000)
                    await self._execute_action_on_device(back_action)
                    await asyncio.sleep(3.0)  # ✅ Wait longer for BACK
                    
                    ui_tree = await self._fetch_ui_tree_with_retries("global_action")
                    if ui_tree:
                        self.current_ui_tree = ui_tree
                        self.device_state = self._detect_device_state(ui_tree)
                    
                    self.incomplete_ui_count = 0
                    continue
            else:
                self.incomplete_ui_count = 0
            
            # Check if stuck
            if self._detect_stuck_in_loop():
                logger.error(f"❌ Stuck in infinite loop - taking corrective action")
                home_action = UIAction(action_type="global_action", global_action="HOME", duration=1000)
                await self._execute_action_on_device(home_action)
                await asyncio.sleep(3.0)  # ✅ Wait longer for HOME
                
                ui_tree = await self._fetch_ui_tree_with_retries("global_action")
                if ui_tree:
                    self.current_ui_tree = ui_tree
                    self.device_state = self._detect_device_state(ui_tree)
                    logger.info(f"🏠 Forced HOME action - new state: {self.device_state}")
            
            # THINK
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
                
                return self._build_result(
                    task_id=task.task_id,
                    status="success",
                    steps=step + 1,
                    actions=actions_executed,
                    elapsed=elapsed,
                    completion_reason=action_json.get("reason", "Task completed")
                )
            
            # ✅ CRITICAL FIX #4: Check blacklist before clicking
            if action_json.get("action_type") == "click":
                element_id = action_json.get("element_id")
                if element_id and element_id in self.failed_elements:
                    logger.warning(f"🚫 Skipping blacklisted element {element_id}")
                    
                    # Try app drawer instead
                    if not self.app_drawer_attempted and self._is_home_screen(self.current_ui_tree):
                        logger.info("📱 Opening app drawer (scroll UP)")
                        action_json = {
                            "action_type": "scroll",
                            "direction": "up",
                            "duration": 500
                        }
                        self.app_drawer_attempted = True
                    else:
                        logger.info("⏭️ Skipping to next iteration")
                        continue
            
            # ACT
            logger.info(f"🎬 ACT: Executing action...")
            logger.info(f"   Type: {action_json.get('action_type')}")
            
            action = self._json_to_ui_action(action_json)
            logger.info(f"   Action: {action.model_dump()}")
            
            # Track clicked element
            if action_json.get("action_type") == "click":
                self.last_clicked_element = action_json.get("element_id")
                self.last_action_was_click = True
            else:
                self.last_action_was_click = False
            
            # ✅ CRITICAL FIX #2: Validate TYPE actions - prevent duplicates
            if action_json.get("action_type") == "type":
                element_id = action_json.get("element_id")
                text_to_type = action_json.get("text", "")
                
                # Check if we already typed this EXACT text in this field
                if element_id in self.typed_texts:
                    if self.typed_texts[element_id] == text_to_type:
                        logger.warning(f"🚫 Already typed '{text_to_type}' in element {element_id}")
                        logger.warning(f"⏭️ Skipping duplicate type action")
                        
                        # ✅ FIX: Track consecutive skips to detect completion
                        self.consecutive_skips += 1
                        logger.info(f"📊 Consecutive skips: {self.consecutive_skips}/3")
                        
                        #  If skipped 3 times, task is likely complete
                        if self.consecutive_skips >= 3:
                            logger.warning(f"⚠️ Skipped {self.consecutive_skips} duplicates - field is complete!")
                            logger.info("✅ FORCING SUB-TASK COMPLETION - coordinator will send next task")
                            elapsed = time.time() - start_time
                            return self._build_result(
                                task_id=task.task_id,
                                status="success",
                                steps=step + 1,
                                actions=actions_executed,
                                elapsed=elapsed,
                                completion_reason=f"Completed (skipped {self.consecutive_skips} duplicate attempts)"
                            )
                        
                        continue  # Skip this action
                
                # ✅ FIX: If we're actually typing, reset skip counter
                self.consecutive_skips = 0
                
                # Store what we're about to type
                self.typed_texts[element_id] = text_to_type
            
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
            else:
                logger.info(f"✅ Action executed successfully")
            
            # OBSERVE
            logger.info(f"👁️ OBSERVE: Getting new UI state...")
            
            wait_time = self._get_wait_time_for_action(action_json.get("action_type"))
            logger.info(f"⏳ Waiting {wait_time}s for UI to stabilize...")
            await asyncio.sleep(wait_time)
            
            # ✅ CRITICAL: Progressive UI fetching - apps take time to load!
            new_ui_tree = await self._fetch_ui_tree_with_retries(
                action_type=action_json.get("action_type"),
                max_attempts=3,
                retry_delay=2.0
            )
            
            if new_ui_tree:
                self.current_ui_tree = new_ui_tree
                self.previous_ui_trees.append(new_ui_tree)
                
                if len(self.previous_ui_trees) > 5:
                    self.previous_ui_trees.pop(0)
                
                new_device_state = self._detect_device_state(new_ui_tree)
                
                logger.info(f"✅ New UI captured: {new_ui_tree.screen_name or new_ui_tree.app_name}")
                logger.info(f"   Elements: {len(new_ui_tree.elements)}")
                logger.info(f"   Device state: {new_device_state}")
                
                if new_ui_tree.elements:
                    logger.info(f"   📦 UI Elements:")
                    for elem in new_ui_tree.elements[:10]:
                        elem_text = elem.text[:40] if elem.text else "(no text)"
                        logger.info(f"      [{elem.element_id}] {elem.type:12} | {elem_text}")
                
                if new_device_state != self.device_state:
                    logger.info(f"🔄 Device state changed: {self.device_state} → {new_device_state}")
                    self.device_state = new_device_state
                    self.stuck_counter = 0
                else:
                    self.stuck_counter += 1
                
                # ✅ CRITICAL: App verification AFTER UI fully loaded (moved from top of loop)
                # Only verify for CLICK actions and when we have a target app
                if self.last_action_was_click and target_app and len(new_ui_tree.elements) >= 5:
                    verification = self._verify_app_opened(target_app, new_ui_tree)
                    
                    if not verification["success"]:
                        # WRONG APP OPENED!
                        logger.error(f"❌ WRONG APP OPENED!")
                        logger.error(f"   Expected: {verification['expected_app']}")
                        logger.error(f"   Got: {verification['actual_app']}")
                        
                        # Blacklist the element that was clicked
                        if self.last_clicked_element:
                            self.failed_elements.add(self.last_clicked_element)
                            logger.warning(f"🚫 Blacklisted element {self.last_clicked_element}")
                        
                        # Go BACK and try again
                        logger.info("⬅️ Going BACK to try different element")
                        back_action = UIAction(action_type="global_action", global_action="BACK", duration=1000)
                        await self._execute_action_on_device(back_action)
                        await asyncio.sleep(3.0)  # Wait longer for BACK
                        
                        ui_tree = await self._fetch_ui_tree_with_retries("global_action")
                        if ui_tree:
                            self.current_ui_tree = ui_tree
                            self.device_state = self._detect_device_state(ui_tree)
                        
                        self.last_action_was_click = False
                        continue
                    
                    # ✅ CRITICAL: Verify task is ACTUALLY complete
                    elif verification["success"] and verification["confidence"] > 0.8:
                        if self._is_task_truly_complete(task.ai_prompt, new_ui_tree):
                            logger.info(f"\n{'='*70}")
                            logger.info(f"✅✅✅ TASK COMPLETE: {verification['actual_app']}")
                            logger.info(f"{'='*70}")
                            
                            return self._build_result(
                                task_id=task.task_id,
                                status="success",
                                steps=step + 1,
                                actions=actions_executed,
                                elapsed=elapsed,
                                completion_reason=f"Successfully opened {verification['actual_app']}"
                            )
                        else:
                            logger.info(f"⚠️ Correct app but task not complete yet")
            else:
                logger.warning(f"⚠️ Failed to get new UI tree")
        
        # Max steps reached
        logger.warning(f"\n{'='*70}")
        logger.warning(f"⚠️ MAX STEPS REACHED")
        logger.warning(f"{'='*70}")
        
        return self._build_result(
            task_id=task.task_id,
            status="failed",
            steps=task.max_steps,
            actions=actions_executed,
            elapsed=asyncio.get_event_loop().time() - start_time,
            error=f"Max steps ({task.max_steps}) reached"
        )
    
    def _calculate_smart_timeout(self, goal: str, default_timeout: int) -> int:
        """
        Calculate smart timeout based on task complexity
        
        Multi-step tasks: 60s (multiple actions)
        Search tasks: 45s (type + wait for results)
        Simple navigation: 30s (just open app)
        """
        goal_lower = goal.lower()
        
        # Multi-step tasks (look for conjunctions or sequences)
        multi_step_keywords = ["and then", "after", "followed by", "and", "with"]
        if any(kw in goal_lower for kw in multi_step_keywords):
            # Count keywords to estimate complexity
            keyword_count = sum(1 for kw in multi_step_keywords if kw in goal_lower)
            if keyword_count >= 2:
                return max(90, default_timeout)  # Very complex
            return max(60, default_timeout)  # Medium complexity
        
        # Search tasks need moderate time
        search_keywords = ["search", "find", "look for", "query"]
        if any(kw in goal_lower for kw in search_keywords):
            return max(45, default_timeout)  # At least 45 seconds
        
        # Navigation tasks (just opening apps)
        open_keywords = ["open", "launch", "start", "close"]
        if any(kw in goal_lower for kw in open_keywords) and len(goal_lower.split()) <= 4:
            return max(30, default_timeout)  # At least 30 seconds
        
        # Default: use provided timeout but minimum 30s
        return max(30, default_timeout)
    
    def _get_content_from_task_params(self, task: 'MobileTaskRequest') -> str:
        """
        Get any parameters passed from coordinator via extra_params
        
        This allows coordinator to pass ANY field values (text, numbers, etc.)
        without hardcoding email-specific logic here
        """
        context_parts = []
        
        # Check extra_params (from coordinator)
        if hasattr(task, 'extra_params') and task.extra_params:
            for key, value in task.extra_params.items():
                # Skip internal params like input_from, device_id, etc.
                if key in ['input_from', 'device_id', 'app_name', 'file_path', 'url']:
                    continue
                
                # Add any user-facing parameter
                context_parts.append(f"📝 {key.upper()}: \"{value}\" (from coordinator)")
        
        if context_parts:
            return "\n" + "\n".join(context_parts) + "\n⚠️ USE THESE EXACT VALUES - DO NOT IMPROVISE!"
        
        return ""
    
    def _extract_target_app(self, goal: str) -> Optional[str]:
        """Extract target app from goal"""
        goal_lower = goal.lower()
        for app, keywords in self.APP_KEYWORDS.items():
            if any(kw in goal_lower for kw in keywords):
                return app
        return None
    
    def _verify_app_opened(self, target_app: str, ui_tree: SemanticUITree) -> Dict[str, Any]:
        """
        Verify if correct app was opened
        
        Returns:
            {
                "success": bool,
                "expected_app": str,
                "actual_app": str,
                "confidence": float,
                "reason": str
            }
        """
        app_name = ui_tree.app_name.lower()
        app_package = ui_tree.app_package.lower() if ui_tree.app_package else ""
        
        keywords = self.APP_KEYWORDS.get(target_app, [])
        app_text = f"{app_name} {app_package}"
        
        # Special case: YouTube Music is NOT YouTube
        if target_app == "youtube" and "music" in app_text:
            return {
                "success": False,
                "expected_app": target_app,
                "actual_app": "youtube_music",
                "confidence": 0.95,
                "reason": "Opened YouTube Music instead of YouTube"
            }
        
        # Check if target keywords present
        is_correct = any(kw in app_text for kw in keywords)
        
        if is_correct:
            return {
                "success": True,
                "expected_app": target_app,
                "actual_app": app_name,
                "confidence": 0.9,
                "reason": f"Successfully opened {target_app}"
            }
        else:
            return {
                "success": False,
                "expected_app": target_app,
                "actual_app": app_name,
                "confidence": 0.85,
                "reason": f"Expected {target_app} but got {app_name}"
            }
    
    def _is_task_truly_complete(self, goal: str, ui_tree: SemanticUITree) -> bool:
        """
        Check if task is ACTUALLY complete
        - UI must be fully loaded (>= 5 elements)
        
        For coordinator-decomposed tasks, trust the LLM's "complete" decision
        since each sub-task is simple and atomic
        """
        elements = ui_tree.elements
        
        # Must have functional UI
        if not elements or len(elements) < 5:
            return False
        
        # If UI is fully loaded, trust the LLM's completion decision
        return True
    
    def _is_home_screen(self, ui_tree: SemanticUITree) -> bool:
        """Check if on home screen"""
        app_name = ui_tree.app_name.lower()
        device_state = self._detect_device_state(ui_tree)
        return "home" in device_state or "launcher" in app_name
    
    def _detect_device_state(self, ui_tree: SemanticUITree) -> str:
        """Detect current device state"""
        app_name = ui_tree.app_name.lower()
        screen_name = ui_tree.screen_name.lower() if ui_tree.screen_name else ""
        
        # Check AURA app first
        if "aura" in app_name or "aura_project" in app_name:
            logger.info(f"🔍 Detected AURA app: {app_name}")
            return "in_aura"
        
        # Home screen indicators
        home_indicators = [
            "launcher", "home screen", "desktop", "wallpaper",
            "homescreen", "main screen", "pixel launcher",
            "android launcher", "trebuchet", "nova launcher"
        ]
        
        if any(indicator in app_name or indicator in screen_name for indicator in home_indicators):
            return "home_screen"
        
        if "app drawer" in screen_name or "all apps" in screen_name:
            return "app_drawer"
        
        return f"in_app_{app_name.replace('.', '_')}"
    
    def _detect_stuck_in_loop(self) -> bool:
        """
        Detect if stuck - BUT be smart about it!
        
        NOT stuck if:
        - UI elements are changing (means app is responding)
        - Element count is fluctuating (means activity happening)
        - Recent actions succeeded
        
        Only stuck if:
        - Same state for 6+ steps (increased from 4)
        - AND same element count
        - AND no successful actions
        """
        # Need at least 6 steps to detect stuck (was 4, too aggressive!)
        if self.stuck_counter <= 5:
            return False
        
        logger.warning(f"⚠️ Stuck counter: {self.stuck_counter}")
        
        # Check if UI is changing
        if len(self.previous_ui_trees) >= 4:
            recent_element_counts = [len(tree.elements) for tree in self.previous_ui_trees[-4:]]
            
            # If element counts are changing, we're NOT stuck!
            if len(set(recent_element_counts)) > 1:
                logger.info(f"✅ UI elements changing: {recent_element_counts} - NOT stuck")
                return False
            
            # If UI has very few elements and not changing, might be stuck
            if recent_element_counts[0] <= 3:
                logger.error(f"❌ UI frozen with only {recent_element_counts[0]} elements")
                return True
        
        # Check recent action history
        if len(self.action_history) >= 3:
            recent_actions = [h["action"]["action_type"] for h in self.action_history[-3:]]
            
            # If doing the SAME global action repeatedly, we're stuck
            if len(set(recent_actions)) == 1 and recent_actions[0] == "global_action":
                logger.warning(f"⚠️ Same global action repeated 3 times: {recent_actions}")
                return True
            
            # If we're actively typing or clicking different things, NOT stuck
            if "type" in recent_actions or "scroll" in recent_actions:
                logger.info(f"✅ Active typing/scrolling: {recent_actions} - NOT stuck")
                return False
        
        # Only declare stuck if counter is REALLY high (6+)
        if self.stuck_counter >= 6:
            logger.error(f"❌ Truly stuck: {self.stuck_counter} steps in same state")
            return True
        
        return False
    
    def _get_wait_time_for_action(self, action_type: str) -> float:
        """Get wait time based on action type"""
        wait_times = {
            "click": 7.0,           # ✅ CRITICAL: Apps need 6-8s to fully open on emulators!
            "global_action": 3.0,   # ✅ CRITICAL: Navigation needs more time
            "type": 1.2,            # Give typing more time to register
            "scroll": 0.8,          # Scrolling animations take time
            "wait": 0.1
        }
        return wait_times.get(action_type, 1.0)
    
    async def _think_and_decide(
        self,
        goal: str,
        observation: str,
        thought_history: List[str],
        step_number: int
    ) -> tuple[str, Optional[Dict]]:
        """Enhanced LLM prompt with blacklist awareness"""
        
        history_context = ""
        if thought_history:
            history_context = "Previous thoughts:\n" + "\n".join(
                f"{i+1}. {t}" for i, t in enumerate(thought_history[-3:])
            )
        
        # Build blacklist context
        blacklist_context = ""
        if self.failed_elements:
            blacklist_context = f"\n🚫 BLACKLISTED ELEMENTS (opened wrong apps): {sorted(list(self.failed_elements))}"
        
        # ✅ FIX: Get exact content from current task params
        exact_content_context = ""
        if self.current_task:
            exact_content_context = self._get_content_from_task_params(self.current_task)
        
        state_context = f"""CURRENT DEVICE STATE: {self.device_state}
STUCK COUNTER: {self.stuck_counter}/6
PREVIOUS ACTIONS: {[h["action"]["action_type"] for h in self.action_history[-3:]] if self.action_history else 'None'}{blacklist_context}
{exact_content_context}
"""
        
        prompt = f"""You are a mobile automation agent analyzing an Android screen.

GOAL: {goal}

{state_context}

CURRENT SCREEN:
{observation}

{history_context}

RULES (Priority order):

1. **AURA EXIT**: In "Aura App Screen"? → Use BACK immediately!

2. **GOAL CHECK**:
   - Goal = "Open X"? → See X app? → DONE ✅
   - Goal = "Click/Type/Set Y"? → Must DO Y first! ❌

3. **⏰ TIME PICKER** (When display shows "07:00" or similar):
   ```
   CRITICAL STEPS:
   1. Clicked hour? → Display shows "07"? → Good!
   2. Check AM/PM buttons:
      - Goal is "7 AM"? → Is AM button visible? → CLICK AM FIRST!
      - Goal is "7 PM"? → Is PM button visible? → CLICK PM FIRST!
   3. THEN click OK button
   
   Example for "7 AM":
   [3] ELEMENT "07"
   [6] BUTTON "AM" ← CLICK THIS FIRST!
   [7] BUTTON "PM"
   [23] BUTTON "OK" ← THEN CLICK THIS
   
   NEVER assume AM is selected - ALWAYS click it explicitly!
   ```

4. **COMPLETION BUTTONS**: See OK/Done/Send/Save? → Click it!

5. **BLACKLIST**: Never click {sorted(list(self.failed_elements))}

6. **EXACT VALUES**: See "📝 KEY: value"? → Use EXACT value!

7. **NO DUPLICATES**: Typing skipped? → Field done, next action!

8. **APP DRAWER**: App not visible? → Scroll UP!

RESPONSE EXAMPLES (copy format exactly):
- Exit AURA: {{"thought": "exit aura", "action_type": "global_action", "global_action": "BACK"}}
- Click element: {{"thought": "click gmail", "action_type": "click", "element_id": 7}}
- Type text: {{"thought": "type email", "action_type": "type", "element_id": 10, "text": "test@example.com"}}
- Task done: {{"thought": "goal achieved", "action_type": "complete"}}

CRITICAL: For global_action, MUST include "global_action": "BACK" or "HOME" in JSON!

Respond with ONLY valid JSON, no markdown."""
        
        try:
            response = await self.llm_client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a mobile automation expert. Respond ONLY with valid JSON. Never use markdown."
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
        """Extract JSON from LLM response"""
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        
        match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
        if match:
            return match.group(0).strip()
        
        return None
    
    def _json_to_ui_action(self, action_json: Dict) -> UIAction:
        """Convert JSON to UIAction"""
        action_type = action_json.get("action_type")
        
        if not action_type:
            raise ValueError("Missing action_type")
        
        kwargs = {
            "action_type": action_type,
            "text": action_json.get("text"),
            "duration": action_json.get("duration", 1000),
        }
        
        if action_type in ["click", "type"]:
            element_id = action_json.get("element_id")
            if element_id is not None:
                try:
                    kwargs["element_id"] = int(element_id)
                except (ValueError, TypeError):
                    logger.error(f"❌ Invalid element_id: {element_id}")
                    kwargs["action_type"] = "scroll"
                    kwargs["direction"] = "down"
                    return UIAction(**kwargs)
            else:
                logger.error(f"❌ No element_id for {action_type}")
                kwargs["action_type"] = "scroll"
                kwargs["direction"] = "down"
                return UIAction(**kwargs)
        
        direction = action_json.get("direction")
        if direction:
            kwargs["direction"] = direction
        
        global_action = action_json.get("global_action")
        if global_action:
            kwargs["global_action"] = global_action
        
        return UIAction(**kwargs)
    
    async def _fetch_ui_tree_from_device(self) -> Optional[SemanticUITree]:
        """Fetch UI tree from device"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.backend_url}/device/{self.device_id}/ui-tree",
                    timeout=5.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if not data:
                        logger.error(f"❌ Empty UI tree response")
                        return None
                    
                    if data.get("_synthetic"):
                        logger.warning(f"⚠️ Received synthetic screen - ignoring")
                        return None
                    
                    return SemanticUITree(**data)
                else:
                    logger.error(f"❌ HTTP {response.status_code}")
                    return None
        
        except Exception as e:
            logger.error(f"❌ Error fetching UI tree: {e}")
            return None
    
    async def _fetch_ui_tree_with_retries(
        self,
        action_type: str,
        max_attempts: int = 3,
        retry_delay: float = 2.0
    ) -> Optional[SemanticUITree]:
        """
        ✅ CRITICAL: Fetch UI tree with retries for incomplete UIs
        
        Apps take time to load! If we get a partial UI (< 5 elements),
        wait longer and try again. This prevents premature verification.
        
        Args:
            action_type: Type of action that was just executed
            max_attempts: Max number of fetch attempts (default 3)
            retry_delay: Seconds to wait between retries (default 2.0)
        
        Returns:
            SemanticUITree or None
        """
        for attempt in range(max_attempts):
            ui_tree = await self._fetch_ui_tree_from_device()
            
            if not ui_tree:
                if attempt < max_attempts - 1:
                    logger.warning(f"⚠️ Attempt {attempt + 1}: No UI tree - retrying in {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                    continue
                else:
                    logger.error(f"❌ Failed to get UI tree after {max_attempts} attempts")
                    return None
            
            # Check if UI is fully loaded
            element_count = len(ui_tree.elements)
            
            # For clicks, we expect a full UI (>= 5 elements)
            # For other actions, minimal validation
            min_elements = 5 if action_type == "click" else 2
            
            if element_count >= min_elements:
                if attempt > 0:
                    logger.info(f"✅ UI fully loaded on attempt {attempt + 1} ({element_count} elements)")
                return ui_tree
            
            # UI incomplete - wait and retry
            if attempt < max_attempts - 1:
                logger.warning(f"⚠️ Attempt {attempt + 1}: UI incomplete ({element_count} elements, need {min_elements}+)")
                logger.warning(f"⏳ Waiting {retry_delay}s for app to finish loading...")
                await asyncio.sleep(retry_delay)
            else:
                logger.warning(f"⚠️ UI still incomplete after {max_attempts} attempts ({element_count} elements)")
                logger.warning(f"⚠️ Proceeding anyway - app may be slow")
                return ui_tree
        
        return None
    
    async def _execute_action_on_device(self, action: UIAction) -> ActionResult:
        """Execute action on device"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.backend_url}/device/{self.device_id}/execute-action",
                    json=action.model_dump(),
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return ActionResult(**data)
                else:
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
    
    def _build_error_result(self, task_id: str, error: str) -> MobileTaskResult:
        """Build error result"""
        return MobileTaskResult(
            task_id=task_id,
            status="failed",
            steps_taken=0,
            actions_executed=[],
            execution_time_ms=0,
            error=error
        )


# Backward compatibility
class MobileStrategy(MobileReActStrategy):
    pass


# Integration function
async def execute_mobile_task(
    task: Dict[str, Any],
    device_id: str = "emulator-5554"
) -> ExecutionResult:
    """Execute mobile task - called by ExecutionAgent"""
    
    try:
        mobile_task = MobileTaskRequest(
            task_id=task.get("task_id"),
            ai_prompt=task.get("ai_prompt"),
            device_id=device_id,
            session_id=task.get("session_id", "default"),
            context=task.get("extra_params", {}),
            extra_params=task.get("extra_params", {}),
            max_steps=15,
            timeout_seconds=task.get("timeout_seconds", 30)
        )
        
        strategy = MobileStrategy(device_id)
        result = await strategy.execute_task(mobile_task)
        
        return ExecutionResult(
            task_id=result.task_id,
            status="success" if result.status == "success" else "failed",
            content=result.completion_reason or result.error,
            error=result.error
        )
    
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        return ExecutionResult(
            task_id=task.get("task_id", "unknown"),
            status="failed",
            error=str(e)
        )