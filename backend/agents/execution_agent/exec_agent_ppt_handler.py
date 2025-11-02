"""
PowerPoint Handler
Extended functionality for PowerPoint automation

Author: Accessibility AI Team
Version: 1.0.0
"""

import time
import os
from typing import List, Dict

from exec_agent_config import Config
from exec_agent_models import ExecutionTask, ExecutionResult
from exec_agent_config import ActionStatus
from datetime import datetime


class PowerPointHandler:
    """
    Handles PowerPoint-specific automation
    Extends LocalStrategy with presentation creation capabilities
    """
    
    def __init__(self, action_layer, vision_layer, logger):
        self.action = action_layer
        self.vision = vision_layer
        self.logger = logger
    
    def create_title_slide(self, task: ExecutionTask, logs: List) -> ExecutionResult:
        """
        Create title slide in PowerPoint
        
        Args:
            task: ExecutionTask with title and subtitle
            logs: Log list
        
        Returns:
            ExecutionResult
        """
        start_time = time.time()
        title = task.params.get("title", "Untitled")
        subtitle = task.params.get("subtitle", "")
        
        try:
            logs.append("Waiting for PowerPoint to load...")
            time.sleep(3)
            
            # Click on title placeholder
            logs.append("Clicking title placeholder")
            self.action.press_key('tab')
            time.sleep(0.5)
            
            # Type title
            logs.append(f"Typing title: {title}")
            self.action.type_text(title, interval=0.1)
            time.sleep(0.5)
            
            # Move to subtitle
            logs.append("Moving to subtitle")
            self.action.press_key('tab')
            time.sleep(0.5)
            
            # Type subtitle
            logs.append(f"Typing subtitle: {subtitle}")
            self.action.type_text(subtitle, interval=0.1)
            
            logs.append("Title slide created successfully")
            
            return ExecutionResult(
                status=ActionStatus.SUCCESS.value,
                task_id=task.task_id,
                context=task.context,
                action="create_title_slide",
                details=f"Created title slide: {title}",
                logs=logs,
                timestamp=datetime.now().isoformat(),
                duration=time.time() - start_time
            )
        
        except Exception as e:
            self.logger.error(f"Error creating title slide: {e}")
            return ExecutionResult(
                status=ActionStatus.FAILED.value,
                task_id=task.task_id,
                context=task.context,
                action="create_title_slide",
                details=f"Failed to create title slide: {e}",
                logs=logs,
                timestamp=datetime.now().isoformat(),
                duration=time.time() - start_time,
                error=str(e)
            )
    
    def add_content_slides(self, task: ExecutionTask, logs: List) -> ExecutionResult:
        """
        Add multiple content slides
        
        Args:
            task: ExecutionTask with slides list
            logs: Log list
        
        Returns:
            ExecutionResult
        """
        start_time = time.time()
        slides = task.params.get("slides", [])
        
        if not slides:
            return ExecutionResult(
                status=ActionStatus.FAILED.value,
                task_id=task.task_id,
                context=task.context,
                action="add_content_slides",
                details="No slides provided",
                logs=logs,
                timestamp=datetime.now().isoformat(),
                duration=time.time() - start_time,
                error="Missing slides parameter"
            )
        
        try:
            for i, slide_data in enumerate(slides, 1):
                logs.append(f"Creating slide {i}/{len(slides)}")
                
                # Add new slide (Ctrl+M)
                self.action.hotkey('ctrl', 'm')
                time.sleep(1)
                
                # Add title
                title = slide_data.get("title", f"Slide {i}")
                logs.append(f"Adding title: {title}")
                self.action.type_text(title, interval=0.1)
                time.sleep(0.5)
                
                # Move to content area
                self.action.press_key('tab')
                time.sleep(0.5)
                
                # Add content
                content = slide_data.get("content", "")
                if content:
                    logs.append(f"Adding content to slide {i}")
                    self.action.type_text(content, interval=0.05)
                    time.sleep(0.5)
            
            logs.append(f"Successfully created {len(slides)} content slides")
            
            return ExecutionResult(
                status=ActionStatus.SUCCESS.value,
                task_id=task.task_id,
                context=task.context,
                action="add_content_slides",
                details=f"Created {len(slides)} content slides",
                logs=logs,
                timestamp=datetime.now().isoformat(),
                duration=time.time() - start_time
            )
        
        except Exception as e:
            self.logger.error(f"Error adding content slides: {e}")
            return ExecutionResult(
                status=ActionStatus.FAILED.value,
                task_id=task.task_id,
                context=task.context,
                action="add_content_slides",
                details=f"Failed to add content slides: {e}",
                logs=logs,
                timestamp=datetime.now().isoformat(),
                duration=time.time() - start_time,
                error=str(e)
            )
    
    def create_new_slide(self, task: ExecutionTask, logs: List) -> ExecutionResult:
        """
        Adds a single new slide with given title and content
        """
        start_time = time.time()
        title = task.params.get("title", "New Slide")
        content = task.params.get("content", "")
        try:
            logs.append("Adding a new slide (Ctrl+M)")
            self.action.hotkey('ctrl', 'm')
            time.sleep(1)
            logs.append(f"Typing title: {title}")
            self.action.type_text(title, interval=0.1)
            time.sleep(0.5)
            self.action.press_key('tab')
            time.sleep(0.5)
            if content:
                logs.append("Typing content")
                self.action.type_text(content, interval=0.05)
                time.sleep(0.5)
            logs.append("Single slide added successfully")
            return ExecutionResult(
                status=ActionStatus.SUCCESS.value,
                task_id=task.task_id,
                context=task.context,
                action="create_new_slide",
                details=f"Added slide: {title}",
                logs=logs,
                timestamp=datetime.now().isoformat(),
                duration=time.time() - start_time
            )
        except Exception as e:
            logs.append(f"Failed to add slide: {e}")
            return ExecutionResult(
                status=ActionStatus.FAILED.value,
                task_id=task.task_id,
                context=task.context,
                action="create_new_slide",
                details=f"Failed to add slide: {e}",
                logs=logs,
                timestamp=datetime.now().isoformat(),
                duration=time.time() - start_time,
                error=str(e)
            )
    
    def create_new_presentation(self, task: ExecutionTask, logs: List) -> ExecutionResult:
        """
        Ensures PowerPoint starts with a new blank presentation (Ctrl+N)
        """
        start_time = time.time()
        try:
            logs.append("Triggering Ctrl+N to open new presentation.")
            self.action.hotkey('ctrl', 'n')
            time.sleep(2)
            return ExecutionResult(
                status=ActionStatus.SUCCESS.value,
                task_id=task.task_id,
                context=task.context,
                action="create_new_presentation",
                details="New blank presentation started.",
                logs=logs,
                timestamp=datetime.now().isoformat(),
                duration=time.time() - start_time
            )
        except Exception as e:
            logs.append(f"Failed to start new presentation: {e}")
            return ExecutionResult(
                status=ActionStatus.FAILED.value,
                task_id=task.task_id,
                context=task.context,
                action="create_new_presentation",
                details=f"Failed: {e}",
                logs=logs,
                timestamp=datetime.now().isoformat(),
                duration=time.time() - start_time,
                error=str(e)
            )
    
    def save_presentation(self, task: ExecutionTask, logs: List) -> ExecutionResult:
        """
        Save PowerPoint presentation
        
        Args:
            task: ExecutionTask with filename and folder
            logs: Log list
        
        Returns:
            ExecutionResult
        """
        start_time = time.time()
        filename = task.params.get("filename", "presentation.pptx")
        folder = task.params.get("folder", os.path.expanduser("~/Desktop"))
        
        try:
            # Open Save As dialog (Ctrl+Shift+S or F12)
            logs.append("Opening Save As dialog")
            self.action.hotkey('ctrl', 'shift', 's')
            time.sleep(2)
            
            # Type full path
            full_path = os.path.join(folder, filename)
            logs.append(f"Saving to: {full_path}")
            
            # Type filename (this will go to filename field)
            self.action.type_text(full_path, interval=0.05)
            time.sleep(1)
            
            # Press Enter to save
            logs.append("Confirming save")
            self.action.press_key('enter')
            time.sleep(2)
            
            # Handle "file already exists" dialog if it appears
            # Press Tab then Enter to confirm overwrite
            self.action.press_key('tab')
            time.sleep(0.3)
            self.action.press_key('enter')
            time.sleep(1)
            
            logs.append(f"Presentation saved: {filename}")
            
            return ExecutionResult(
                status=ActionStatus.SUCCESS.value,
                task_id=task.task_id,
                context=task.context,
                action="save_presentation",
                details=f"Saved presentation to: {full_path}",
                logs=logs,
                timestamp=datetime.now().isoformat(),
                duration=time.time() - start_time,
                metadata={"file_path": full_path}
            )
        
        except Exception as e:
            self.logger.error(f"Error saving presentation: {e}")
            return ExecutionResult(
                status=ActionStatus.FAILED.value,
                task_id=task.task_id,
                context=task.context,
                action="save_presentation",
                details=f"Failed to save presentation: {e}",
                logs=logs,
                timestamp=datetime.now().isoformat(),
                duration=time.time() - start_time,
                error=str(e)
            )
    
    def close_app(self, task: ExecutionTask, logs: List) -> ExecutionResult:
        """
        Close application (Alt+F4)
        
        Args:
            task: ExecutionTask
            logs: Log list
        
        Returns:
            ExecutionResult
        """
        start_time = time.time()
        app_name = task.params.get("app_name", "Application")
        
        try:
            logs.append(f"Closing {app_name}")
            self.action.hotkey('alt', 'F4')
            time.sleep(1)
            
            # Handle save prompt if it appears
            # Press 'n' for "Don't Save" or Tab+Enter
            self.action.press_key('n')
            time.sleep(0.5)
            
            logs.append(f"{app_name} closed successfully")
            
            return ExecutionResult(
                status=ActionStatus.SUCCESS.value,
                task_id=task.task_id,
                context=task.context,
                action="close_app",
                details=f"Closed {app_name}",
                logs=logs,
                timestamp=datetime.now().isoformat(),
                duration=time.time() - start_time
            )
        
        except Exception as e:
            self.logger.error(f"Error closing app: {e}")
            return ExecutionResult(
                status=ActionStatus.FAILED.value,
                task_id=task.task_id,
                context=task.context,
                action="close_app",
                details=f"Failed to close {app_name}: {e}",
                logs=logs,
                timestamp=datetime.now().isoformat(),
                duration=time.time() - start_time,
                error=str(e)
            )


def integrate_powerpoint_handler(local_strategy, logger):
    """
    Integrate PowerPoint handler into LocalStrategy
    
    Args:
        local_strategy: LocalStrategy instance
        logger: Logger instance
    """
    ppt_handler = PowerPointHandler(
        local_strategy.action,
        local_strategy.vision,
        logger
    )
    
    # Add PowerPoint methods to LocalStrategy
    local_strategy.ppt_handler = ppt_handler
    
    # Override execute to handle PowerPoint actions
    original_execute = local_strategy.execute
    
    def enhanced_execute(task):
        action_type = task.params.get("action_type", "")
        logs = []
        
        # PowerPoint-specific actions
        if action_type == "create_title_slide":
            return ppt_handler.create_title_slide(task, logs)
        
        elif action_type == "add_content_slides":
            return ppt_handler.add_content_slides(task, logs)
        
        elif action_type == "create_new_slide":
            return ppt_handler.create_new_slide(task, logs)
        
        elif action_type == "create_new_presentation":
            return ppt_handler.create_new_presentation(task, logs)
        
        elif action_type == "save_presentation":
            return ppt_handler.save_presentation(task, logs)
        
        elif action_type == "close_app":
            return ppt_handler.close_app(task, logs)
        
        # Fall back to original execute
        else:
            return original_execute(task)
    
    local_strategy.execute = enhanced_execute
    
    return local_strategy
