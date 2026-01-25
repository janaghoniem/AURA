"""
Accessibility Automation Handler
Handles direct automation for known apps like Gmail, WhatsApp, etc.
Uses the AccessibilityService on Android for reliable, fast automation.

This handler checks if a task can be automated using pre-defined flows,
then triggers the Android AccessibilityService to execute the automation.
"""

import logging
import asyncio
import httpx
from typing import Optional, Dict, Any
from agents.utils.device_protocol import MobileTaskRequest, MobileTaskResult

logger = logging.getLogger(__name__)


class AccessibilityAutomationHandler:
    """
    Handles automation tasks that can be executed directly via AccessibilityService
    without needing the ReAct loop.
    
    Supported automations:
    - Gmail: Open app, compose email, fill fields, send
    - WhatsApp: Open app, send message
    - (Add more as needed)
    """
    
    # Map of automation types to their triggers
    AUTOMATION_PATTERNS = {
        "gmail": [
            "open gmail",
            "launch gmail",
            "start gmail",
            "open the gmail app"
        ],
        "whatsapp": [
            "open whatsapp",
            "launch whatsapp",
            "start whatsapp"
        ]
    }
    
    def __init__(self, device_id: str = "default_device"):
        """
        Initialize handler
        
        Args:
            device_id: Android device to target
        """
        self.device_id = device_id
        self.backend_url = "http://localhost:8000"
        self.pending_automations: Dict[str, asyncio.Future] = {}
        logger.info(f"✅ Initialized AccessibilityAutomationHandler for device {device_id}")
    
    def can_handle_task(self, ai_prompt: str) -> Optional[str]:
        """
        Check if this handler can automate the given task
        
        Args:
            ai_prompt: Natural language task description
            
        Returns:
            Automation type (e.g., "gmail") if supported, None otherwise
        """
        prompt_lower = ai_prompt.lower().strip()
        
        for automation_type, patterns in self.AUTOMATION_PATTERNS.items():
            for pattern in patterns:
                if pattern in prompt_lower:
                    logger.info(f"✅ Task '{ai_prompt}' can be handled by AccessibilityService ({automation_type})")
                    return automation_type
        
        logger.info(f"❌ Task '{ai_prompt}' cannot be handled by AccessibilityService")
        return None
    
    async def execute_automation(
        self,
        task: MobileTaskRequest
    ) -> MobileTaskResult:
        """
        Execute automation via AccessibilityService
        
        Args:
            task: Mobile task request
            
        Returns:
            Result of automation execution
        """
        automation_type = self.can_handle_task(task.ai_prompt)
        
        if not automation_type:
            return MobileTaskResult(
                task_id=task.task_id,
                status="error",
                steps_taken=0,
                actions_executed=[],
                execution_time_ms=0,
                error="Task cannot be automated via AccessibilityService"
            )
        
        logger.info(f"📱 Triggering AccessibilityService automation: {automation_type}")
        logger.info(f"   Action: START_AUTOMATION")
        logger.info(f"   Task ID: {task.task_id}")
        
        try:
            # Send broadcast to Android device to trigger AccessibilityService
            await self._trigger_android_automation(
                task_id=task.task_id,
                automation_type=automation_type,
                device_id=task.device_id
            )
            
            # Wait for result from Android
            logger.info(f"✅ Automation command sent, waiting for result...")
            
            # Create future to wait for Android response
            future = asyncio.Future()
            self.pending_automations[task.task_id] = future
            
            try:
                # Wait for result with timeout
                result = await asyncio.wait_for(future, timeout=task.timeout_seconds)
                
                return MobileTaskResult(
                    task_id=task.task_id,
                    status="success",
                    steps_taken=1,
                    actions_executed=[],
                    execution_time_ms=int(result.get("execution_time_ms", 0)),
                    completion_reason=f"Automation completed via AccessibilityService ({automation_type})"
                )
            
            except asyncio.TimeoutError:
                logger.error(f"❌ Automation timed out after {task.timeout_seconds}s")
                return MobileTaskResult(
                    task_id=task.task_id,
                    status="timeout",
                    steps_taken=0,
                    actions_executed=[],
                    execution_time_ms=task.timeout_seconds * 1000,
                    error=f"Automation timed out after {task.timeout_seconds}s"
                )
            
            finally:
                # Clean up future
                if task.task_id in self.pending_automations:
                    del self.pending_automations[task.task_id]
        
        except Exception as e:
            logger.error(f"❌ Error executing automation: {e}", exc_info=True)
            return MobileTaskResult(
                task_id=task.task_id,
                status="error",
                steps_taken=0,
                actions_executed=[],
                execution_time_ms=0,
                error=str(e)
            )
    
    async def _trigger_android_automation(
        self,
        task_id: str,
        automation_type: str,
        device_id: str
    ):
        """
        Send HTTP request to trigger AccessibilityService on Android
        
        Args:
            task_id: Task identifier
            automation_type: Type of automation (gmail, whatsapp, etc.)
            device_id: Android device ID
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.backend_url}/device/{device_id}/broadcast",
                    json={
                        "action": "com.example.aura_project.START_AUTOMATION",
                        "task_id": task_id,
                        "automation_type": automation_type
                    },
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    logger.info(f"✅ Broadcast sent: START_AUTOMATION")
                else:
                    logger.error(f"❌ Broadcast failed: {response.status_code}")
                    raise Exception(f"Failed to send broadcast: {response.status_code}")
        
        except Exception as e:
            logger.error(f"❌ Error sending broadcast: {e}")
            raise
    
    def on_automation_complete(self, task_id: str, result: Dict[str, Any]):
        """
        Callback when Android reports automation completion
        
        Args:
            task_id: Task identifier
            result: Automation result data
        """
        if task_id in self.pending_automations:
            future = self.pending_automations[task_id]
            if not future.done():
                future.set_result(result)
                logger.info(f"✅ Automation result received for task {task_id}")