"""
Execution Strategies Module (Updated)
Implements different execution strategies: Local, Web, System

Author: Accessibility AI Team
Version: 1.1.0
"""

import os
import time
import platform
import subprocess
from datetime import datetime
from typing import List
from difflib import get_close_matches


# from backend.agents.execution_agent.core.exec_agent_config import Config, ActionStatus
# from backend.agents.execution_agent.core.exec_agent_models import ExecutionTask, ExecutionResult
# from backend.agents.execution_agent.core.exec_agent_deps import (
#     PYWINAUTO_AVAILABLE, SELENIUM_AVAILABLE,
#     Application, webdriver, By, WebDriverWait, EC
# )

from ..core.exec_agent_config import Config, ActionStatus, StatusCode, ExecutionContext
from ..core.exec_agent_models import ExecutionTask, ExecutionResult
from ..core.exec_agent_deps import(
    PYWINAUTO_AVAILABLE, SELENIUM_AVAILABLE,
    Application, webdriver, By, WebDriverWait, EC
)
from ..layers.exec_agent_vision import VisionLayer
from ..layers.exec_agent_action import ActionLayer
from ..layers.exec_agent_safety import SafetyLayer



class LocalStrategy:
    """Execute local Windows automation tasks"""
    
    def __init__(self, logger, vision_layer, action_layer, safety_layer):
        self.logger = logger
        self.vision = vision_layer
        self.action = action_layer
        self.safety = safety_layer
        
    def _map_action_type(self, input_action: str) -> str:
        """Map similar or fuzzy action names to standard ones"""
        
        base_actions = {
            "open_app": ["open", "launch", "start", "run"],
            "wait_for_app": ["wait", "delay", "pause"],
            "click_element": ["click", "press", "tap"],
            "double_click_element": ["double_click", "dblclick"],
            "type_text": ["type", "input", "write", "enter_text"],
            "press_key": ["press_key", "key_press"],
            "hotkey": ["hotkey", "shortcut", "combo"],
            "move_mouse": ["move_mouse", "move_cursor"],
            "scroll": ["scroll", "wheel"],
            "drag_to": ["drag", "drag_to"],
            "send_message": ["send", "message", "chat"],
            "join_voice_channel": ["join_voice", "connect_voice"],
            "leave_voice_channel": ["leave_voice", "disconnect_voice"],
            "wait": ["sleep", "pause"]
        }
        
        # Normalize input
        action_lower = input_action.lower()
        
        # Direct match
        if action_lower in base_actions:
            return action_lower
        
        # Fuzzy partial match
        for standard_action, keywords in base_actions.items():
            if any(k in action_lower for k in keywords):
                return standard_action
        
        # Special mapping for common keyboard operations
        if any(k in action_lower for k in ["copy", "cut", "paste", "save", "select_all"]):
            return "hotkey"
        
        # Fallback: fuzzy closest match
        possible = get_close_matches(action_lower, base_actions.keys(), n=1, cutoff=0.6)
        if possible:
            return possible[0]
        
        # If no match found
        return input_action
    

    
    def execute(self, task: ExecutionTask) -> ExecutionResult:
        """Execute local automation task"""
        start_time = time.time()
        logs = []

        try:
            # Get the original action and normalize it
            input_action = task.params.get("action_type", "")
            action_type = self._map_action_type(input_action)

            # --- Basic Application Actions ---
            if action_type == "open_app":
                return self._open_application(task, logs, start_time)

            elif action_type == "wait_for_app":
                return self._wait_for_app(task, logs, start_time)

            # --- Element Interaction Actions ---
            elif action_type == "click_element":
                return self._click_element(task, logs, start_time)

            elif action_type == "double_click_element":
                return self._double_click_element(task, logs, start_time)

            # --- Text Input Actions ---
            elif action_type == "type_text":
                return self._type_text(task, logs, start_time)

            # --- Keyboard Actions ---
            elif action_type == "press_key":
                return self._press_key(task, logs, start_time)

            # --- Smart Handling for Common Shortcuts ---
            elif input_action.lower() in ["copy", "copy_text"]:
                task.params["keys"] = ["ctrl", "c"]
                return self._execute_hotkey(task, logs, start_time)

            elif input_action.lower() in ["paste", "paste_text"]:
                task.params["keys"] = ["ctrl", "v"]
                return self._execute_hotkey(task, logs, start_time)

            elif input_action.lower() in ["cut", "cut_text"]:
                task.params["keys"] = ["ctrl", "x"]
                return self._execute_hotkey(task, logs, start_time)

            elif input_action.lower() in ["select_all", "select_text"]:
                task.params["keys"] = ["ctrl", "a"]
                return self._execute_hotkey(task, logs, start_time)

            elif input_action.lower() in ["save", "save_file"]:
                task.params["keys"] = ["ctrl", "s"]
                return self._execute_hotkey(task, logs, start_time)

            # --- Hotkey Actions ---
            elif action_type == "hotkey":
                return self._execute_hotkey(task, logs, start_time)

            # --- Mouse Actions ---
            elif action_type == "move_mouse":
                return self._move_mouse(task, logs, start_time)

            elif action_type == "scroll":
                return self._scroll(task, logs, start_time)

            elif action_type == "drag_to":
                return self._drag_to(task, logs, start_time)

            # --- Messaging Actions ---
            elif action_type == "send_message":
                return self._send_message(task, logs, start_time)

            # --- Voice Channel Actions ---
            elif action_type == "join_voice_channel":
                return self._join_voice_channel(task, logs, start_time)

            elif action_type == "leave_voice_channel":
                return self._leave_voice_channel(task, logs, start_time)

            # --- Wait Action ---
            elif action_type == "wait":
                return self._wait(task, logs, start_time)

            # --- Unknown Action ---
            else:
                return ExecutionResult(
                    status=ActionStatus.FAILED.value,
                    task_id=task.task_id,
                    context=task.context,
                    action=task.action_type,
                    details=f"Unknown action type: {action_type}",
                    logs=logs,
                    timestamp=datetime.now().isoformat(),
                    duration=time.time() - start_time,
                    error="Unknown action type"
                )

        except Exception as e:
            self.logger.error(f"Local execution error: {e}")
            screenshot = self.vision.capture_screen()

            return ExecutionResult(
                status=ActionStatus.FAILED.value,
                task_id=task.task_id,
                context=task.context,
                action=task.action_type,
                details=f"Execution failed: {str(e)}",
                logs=logs,
                timestamp=datetime.now().isoformat(),
                duration=time.time() - start_time,
                error=str(e),
                screenshot_path=screenshot
            )


    # ==================== APPLICATION ACTIONS ====================
    
    def _open_application(self, task: ExecutionTask, logs: List, start_time: float) -> ExecutionResult:
        """Open Windows application"""
        app_name = task.params.get("app_name")
        
        if not app_name:
            return self._create_error_result(task, logs, start_time, "Missing app_name parameter")
        
        try:
            logs.append(f"Opening {app_name} via Start Menu")
            self.action.press_key('win')
            time.sleep(1)
            
            self.action.type_text(app_name, interval=0.1)
            time.sleep(1)
            
            self.action.press_key('enter')
            time.sleep(3)
            
            logs.append(f"Successfully opened {app_name}")
            
            return ExecutionResult(
                status=ActionStatus.SUCCESS.value,
                task_id=task.task_id,
                context=task.context,
                action="open_app",
                details=f"Application '{app_name}' opened successfully",
                logs=logs,
                timestamp=datetime.now().isoformat(),
                duration=time.time() - start_time
            )
        
        except Exception as e:
            return self._create_error_result(task, logs, start_time, f"Failed to open {app_name}: {e}")
    
    def _wait_for_app(self, task: ExecutionTask, logs: List, start_time: float) -> ExecutionResult:
        """Wait for application to load"""
        app_name = task.params.get("app_name", "Application")
        wait_time = task.params.get("wait_time", 5)
        
        try:
            logs.append(f"Waiting {wait_time}s for {app_name} to load")
            time.sleep(wait_time)
            logs.append(f"{app_name} should be loaded")
            
            return self._create_success_result(task, logs, start_time, f"Waited for {app_name}")
        
        except Exception as e:
            return self._create_error_result(task, logs, start_time, f"Wait failed: {e}")
    
    # ==================== ELEMENT INTERACTION ACTIONS ====================
    
    def _click_element(self, task: ExecutionTask, logs: List, start_time: float) -> ExecutionResult:
        """Click UI element with multi-strategy fallback"""
        element_desc = task.params.get("element", {})
        
        logs.append("Attempting to locate element")
        
        # Strategy 1: Try UIA (if window_title provided)
        if PYWINAUTO_AVAILABLE and element_desc.get("window_title"):
            try:
                app = Application(backend='uia').connect(title_re=f".*{element_desc['window_title']}.*")
                window = app.top_window()
                
                vision_result = self.vision.detect_element_uia(window, element_desc)
                
                if vision_result.element_found:
                    logs.append(f"Element found via UIA")
                    if self.action.click(vision_result.coordinates):
                        logs.append("Click successful")
                        return self._create_success_result(task, logs, start_time, "Element clicked via UIA")
            except Exception as e:
                logs.append(f"UIA method failed: {e}")
        
        # Strategy 2: Try OCR (if text provided)
        if element_desc.get("text"):
            logs.append("Falling back to OCR detection")
            vision_result = self.vision.detect_element_ocr(element_desc["text"])
            
            if vision_result.element_found and vision_result.confidence > Config.OCR_CONFIDENCE_THRESHOLD:
                logs.append(f"Element found via OCR (confidence: {vision_result.confidence:.2f})")
                if self.action.click(vision_result.coordinates):
                    logs.append("Click successful")
                    return self._create_success_result(task, logs, start_time, "Element clicked via OCR")
        
        # Strategy 3: Try template matching (if image_path provided)
        if element_desc.get("image_path"):
            logs.append("Falling back to Computer Vision")
            vision_result = self.vision.detect_element_image(element_desc["image_path"])
            
            if vision_result.element_found:
                logs.append("Element found via CV")
                if self.action.click(vision_result.coordinates):
                    logs.append("Click successful")
                    return self._create_success_result(task, logs, start_time, "Element clicked via CV")
        
        # All strategies failed
        screenshot = self.vision.capture_screen()
        return ExecutionResult(
            status=ActionStatus.FAILED.value,
            task_id=task.task_id,
            context=task.context,
            action="click_element",
            details="Element not found with any detection method",
            logs=logs,
            timestamp=datetime.now().isoformat(),
            duration=time.time() - start_time,
            error="Element not found",
            screenshot_path=screenshot
        )
    
    def _double_click_element(self, task: ExecutionTask, logs: List, start_time: float) -> ExecutionResult:
        """Double-click UI element"""
        element_desc = task.params.get("element", {})
        
        logs.append("Attempting to locate element for double-click")
        
        # Try OCR first
        if element_desc.get("text"):
            vision_result = self.vision.detect_element_ocr(element_desc["text"])
            
            if vision_result.element_found and vision_result.confidence > Config.OCR_CONFIDENCE_THRESHOLD:
                logs.append(f"Element found via OCR")
                if self.action.double_click(vision_result.coordinates):
                    logs.append("Double-click successful")
                    return self._create_success_result(task, logs, start_time, "Element double-clicked")
        
        # Try image matching
        if element_desc.get("image_path"):
            vision_result = self.vision.detect_element_image(element_desc["image_path"])
            
            if vision_result.element_found:
                logs.append("Element found via CV")
                if self.action.double_click(vision_result.coordinates):
                    logs.append("Double-click successful")
                    return self._create_success_result(task, logs, start_time, "Element double-clicked")
        
        return self._create_error_result(task, logs, start_time, "Element not found for double-click")
    
    # ==================== TEXT INPUT ACTIONS ====================
    
    def _type_text(self, task: ExecutionTask, logs: List, start_time: float) -> ExecutionResult:
        """Type text into focused field"""
        text = task.params.get("text")
        interval = task.params.get("interval", None)
        
        if not text:
            return self._create_error_result(task, logs, start_time, "Missing text parameter")
        
        try:
            logs.append(f"Typing text: {text[:50]}...")
            
            if self.action.type_text(text, interval=interval):
                logs.append("Text typed successfully")
                return self._create_success_result(task, logs, start_time, "Text typed successfully")
            else:
                return self._create_error_result(task, logs, start_time, "Failed to type text")
        
        except Exception as e:
            return self._create_error_result(task, logs, start_time, f"Error typing text: {e}")
    
    # ==================== KEYBOARD ACTIONS ====================
    
    def _press_key(self, task: ExecutionTask, logs: List, start_time: float) -> ExecutionResult:
        """Press a single key - delegates to ActionLayer"""
        key = task.params.get("key")
        
        if not key:
            return self._create_error_result(task, logs, start_time, "Missing key parameter")
        
        try:
            logs.append(f"Pressing key: {key}")
            # Delegate to ActionLayer
            if self.action.press_key(key):
                logs.append("Key pressed successfully")
                return self._create_success_result(task, logs, start_time, f"Key '{key}' pressed")
            else:
                return self._create_error_result(task, logs, start_time, "Failed to press key")
        
        except Exception as e:
            return self._create_error_result(task, logs, start_time, f"Key press failed: {e}")
    
    def _execute_hotkey(self, task: ExecutionTask, logs: List, start_time: float) -> ExecutionResult:
        """Execute keyboard hotkey combination - delegates to ActionLayer"""
        keys = task.params.get("keys", [])
        
        if not keys:
            return self._create_error_result(task, logs, start_time, "Missing keys parameter")
        
        try:
            logs.append(f"Executing hotkey: {'+'.join(keys)}")
            # Delegate to ActionLayer
            if self.action.hotkey(*keys):
                logs.append("Hotkey executed successfully")
                return self._create_success_result(task, logs, start_time, f"Hotkey {'+'.join(keys)} executed")
            else:
                return self._create_error_result(task, logs, start_time, "Failed to execute hotkey")
        
        except Exception as e:
            return self._create_error_result(task, logs, start_time, f"Hotkey failed: {e}")
    
    # ==================== MOUSE ACTIONS ====================
    
    def _move_mouse(self, task: ExecutionTask, logs: List, start_time: float) -> ExecutionResult:
        """Move mouse to coordinates - delegates to ActionLayer"""
        coordinates = task.params.get("coordinates")
        duration = task.params.get("duration", 0.5)
        
        if not coordinates or len(coordinates) != 2:
            return self._create_error_result(task, logs, start_time, "Missing or invalid coordinates parameter")
        
        try:
            logs.append(f"Moving mouse to {coordinates}")
            # Delegate to ActionLayer
            if self.action.move_to(tuple(coordinates), duration=duration):
                logs.append("Mouse moved successfully")
                return self._create_success_result(task, logs, start_time, f"Mouse moved to {coordinates}")
            else:
                return self._create_error_result(task, logs, start_time, "Failed to move mouse")
        
        except Exception as e:
            return self._create_error_result(task, logs, start_time, f"Mouse move failed: {e}")
    
    def _scroll(self, task: ExecutionTask, logs: List, start_time: float) -> ExecutionResult:
        """Scroll mouse wheel - delegates to ActionLayer"""
        clicks = task.params.get("clicks", 3)
        
        try:
            direction = "up" if clicks > 0 else "down"
            logs.append(f"Scrolling {abs(clicks)} clicks {direction}")
            
            # Delegate to ActionLayer
            if self.action.scroll(clicks):
                logs.append("Scroll successful")
                return self._create_success_result(task, logs, start_time, f"Scrolled {abs(clicks)} clicks {direction}")
            else:
                return self._create_error_result(task, logs, start_time, "Failed to scroll")
        
        except Exception as e:
            return self._create_error_result(task, logs, start_time, f"Scroll failed: {e}")
    
    def _drag_to(self, task: ExecutionTask, logs: List, start_time: float) -> ExecutionResult:
        """Drag mouse to coordinates - delegates to ActionLayer"""
        coordinates = task.params.get("coordinates")
        duration = task.params.get("duration", 0.5)
        
        if not coordinates or len(coordinates) != 2:
            return self._create_error_result(task, logs, start_time, "Missing or invalid coordinates parameter")
        
        try:
            logs.append(f"Dragging mouse to {coordinates}")
            # Delegate to ActionLayer
            if self.action.drag_to(tuple(coordinates), duration=duration):
                logs.append("Drag successful")
                return self._create_success_result(task, logs, start_time, f"Dragged to {coordinates}")
            else:
                return self._create_error_result(task, logs, start_time, "Failed to drag")
        
        except Exception as e:
            return self._create_error_result(task, logs, start_time, f"Drag failed: {e}")
    
    # ==================== MESSAGING ACTIONS ====================
    
    def _send_message(self, task: ExecutionTask, logs: List, start_time: float) -> ExecutionResult:
        """Send message (Discord/WhatsApp example)"""
        platform_name = task.params.get("platform", "discord")
        server_name = task.params.get("server_name")
        channel_image = task.params.get("channel_image")
        message = task.params.get("message")
        
        try:
            logs.append(f"Sending message via {platform_name}")
            
            # Open Quick Switcher (Discord)
            # if platform_name.lower() == "discord":
            #     self.action.hotkey('ctrl', 'k')
            #     time.sleep(1)
            #     logs.append("Opened quick switcher")
                
            #     # Type server name
            #     if server_name:
            #         self.action.type_text(server_name, interval=0.1)
            #         time.sleep(1)
                    
            #         self.action.press_key('enter')
            #         time.sleep(3)
            #         logs.append(f"Entered server: {server_name}")
                
            #     # Click channel using image recognition
            #     if channel_image:
            #         vision_result = self.vision.detect_element_image(channel_image)
                    
            #         if vision_result.element_found:
            #             self.action.click(vision_result.coordinates)
            #             time.sleep(2)
            #             logs.append("Joined channel")
            #         else:
            #             return self._create_error_result(task, logs, start_time, "Channel not found")
                
            #     # Send message
            #     self.action.press_key('tab')
                # time.sleep(1)
            
            # Type and send message
            if message:
                self.action.type_text(message, interval=0.05)
                self.action.press_key('enter')
                logs.append(f"Message sent: {message}")
            
            return self._create_success_result(task, logs, start_time, f"Message sent via {platform_name}")
        
        except Exception as e:
            return self._create_error_result(task, logs, start_time, f"Failed to send message: {e}")
    
    # ==================== VOICE CHANNEL ACTIONS ====================
    
    def _join_voice_channel(self, task: ExecutionTask, logs: List, start_time: float) -> ExecutionResult:
        """Join Discord voice channel"""
        channel_name = task.params.get("channel_name")
        
        if not channel_name:
            return self._create_error_result(task, logs, start_time, "Missing channel_name parameter")
        
        try:
            logs.append(f"Attempting to join voice channel: {channel_name}")
            
            # Try to find and click voice channel using OCR
            vision_result = self.vision.detect_element_ocr(channel_name)
            
            if vision_result.element_found:
                # Double-click to join
                self.action.click(vision_result.coordinates)
                time.sleep(0.5)
                self.action.click(vision_result.coordinates)
                time.sleep(2)
                
                logs.append(f"Joined voice channel: {channel_name}")
                return self._create_success_result(task, logs, start_time, f"Joined {channel_name}")
            else:
                return self._create_error_result(task, logs, start_time, f"Voice channel '{channel_name}' not found")
        
        except Exception as e:
            return self._create_error_result(task, logs, start_time, f"Failed to join voice: {e}")
    
    def _leave_voice_channel(self, task: ExecutionTask, logs: List, start_time: float) -> ExecutionResult:
        """Leave Discord voice channel"""
        try:
            logs.append("Leaving voice channel")
            
            # Click disconnect button (usually ESC or clicking channel again)
            self.action.press_key('esc')
            time.sleep(1)
            
            logs.append("Left voice channel")
            return self._create_success_result(task, logs, start_time, "Left voice channel")
        
        except Exception as e:
            return self._create_error_result(task, logs, start_time, f"Failed to leave voice: {e}")
    
    # ==================== UTILITY ACTIONS ====================
    
    def _wait(self, task: ExecutionTask, logs: List, start_time: float) -> ExecutionResult:
        """Simple wait/delay"""
        duration = task.params.get("duration", 1)
        
        try:
            logs.append(f"Waiting for {duration} seconds")
            time.sleep(duration)
            logs.append("Wait completed")
            
            return self._create_success_result(task, logs, start_time, f"Waited {duration}s")
        
        except Exception as e:
            return self._create_error_result(task, logs, start_time, f"Wait failed: {e}")
    
    # ==================== HELPER METHODS ====================
    
    def _create_success_result(self, task, logs, start_time, details):
        """Helper to create success result"""
        return ExecutionResult(
            status=ActionStatus.SUCCESS.value,
            task_id=task.task_id,
            context=task.context,
            action=task.action_type,
            details=details,
            logs=logs,
            timestamp=datetime.now().isoformat(),
            duration=time.time() - start_time
        )
    
    def _create_error_result(self, task, logs, start_time, error):
        """Helper to create error result"""
        logs.append(error)
        return ExecutionResult(
            status=ActionStatus.FAILED.value,
            task_id=task.task_id,
            context=task.context,
            action=task.action_type,
            details=error,
            logs=logs,
            timestamp=datetime.now().isoformat(),
            duration=time.time() - start_time,
            error=error
        )

