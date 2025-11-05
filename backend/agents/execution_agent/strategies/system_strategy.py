
import os
import time
import platform
import subprocess
from datetime import datetime
from typing import List

# from backend.agents.execution_agent.core.exec_agent_config import Config, ActionStatus
# from backend.agents.execution_agent.core.exec_agent_models import ExecutionTask, ExecutionResult
# from backend.agents.execution_agent.core.exec_agent_deps import (
#     PYWINAUTO_AVAILABLE, SELENIUM_AVAILABLE,
#     Application, webdriver, By, WebDriverWait, EC
# )
# ✅ CORRECT:
from core.exec_agent_config import Config, ActionStatus, StatusCode, RiskLevel
from core.exec_agent_models import ExecutionTask, ExecutionResult
from layers.exec_agent_safety import SafetyLayer

class SystemStrategy:
    """Execute system-level commands"""
    
    def __init__(self, logger, safety_layer):
        self.logger = logger
        self.safety = safety_layer
    
    def execute(self, task: ExecutionTask) -> ExecutionResult:
        """Execute system command"""
        start_time = time.time()
        logs = []
        
        try:
            action_type = task.params.get("action_type", "")
            
            # Handle specific system actions
            if action_type == "create_folder":
                return self._create_folder(task, logs, start_time)
            
            elif action_type == "verify_file":
                return self._verify_file(task, logs, start_time)
            
            elif action_type == "save_file":
                return self._save_file(task, logs, start_time)
            
            elif action_type == "log_completion":
                return self._log_completion(task, logs, start_time)
            
            # Handle generic commands
            command = task.params.get("command")
            
            if not command:
                return self._create_error_result(task, logs, start_time, "Missing command parameter")
            
            # Check risk level
            risk = self.safety.assess_risk(command, task.params)
            
            if self.safety.requires_confirmation(risk):
                logs.append(f"High-risk command detected: {risk.value}")
                return ExecutionResult(
                    status=ActionStatus.AWAITING_CONFIRMATION.value,
                    task_id=task.task_id,
                    context=task.context,
                    action="system_command",
                    details=f"Command requires confirmation: {command}",
                    logs=logs,
                    timestamp=datetime.now().isoformat(),
                    duration=time.time() - start_time,
                    metadata={"risk_level": risk.value}
                )
            
            # Execute command
            logs.append(f"Executing: {command}")
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=task.timeout
            )
            
            if result.returncode == 0:
                logs.append("Command executed successfully")
                return ExecutionResult(
                    status=ActionStatus.SUCCESS.value,
                    task_id=task.task_id,
                    context=task.context,
                    action="system_command",
                    details=f"Command output: {result.stdout[:200]}",
                    logs=logs,
                    timestamp=datetime.now().isoformat(),
                    duration=time.time() - start_time,
                    metadata={"stdout": result.stdout, "stderr": result.stderr}
                )
            else:
                return self._create_error_result(task, logs, start_time, result.stderr)
        
        except subprocess.TimeoutExpired:
            return self._create_error_result(task, logs, start_time, "Command execution timed out")
        
        except Exception as e:
            return self._create_error_result(task, logs, start_time, f"System command failed: {e}")
    
    # ==================== FILE SYSTEM ACTIONS ====================
    
    def _create_folder(self, task, logs, start_time):
        """Create folder on filesystem"""
        folder_path = task.params.get("folder_path")
        
        if not folder_path:
            return self._create_error_result(task, logs, start_time, "Missing folder_path parameter")
        
        try:
            os.makedirs(folder_path, exist_ok=True)
            logs.append(f"Created folder: {folder_path}")
            
            return ExecutionResult(
                status=ActionStatus.SUCCESS.value,
                task_id=task.task_id,
                context=task.context,
                action="create_folder",
                details=f"Folder created: {folder_path}",
                logs=logs,
                timestamp=datetime.now().isoformat(),
                duration=time.time() - start_time,
                metadata={"folder_path": folder_path}
            )
        
        except Exception as e:
            return self._create_error_result(task, logs, start_time, f"Failed to create folder: {e}")
    
    def _verify_file(self, task, logs, start_time):
        """Verify file exists in folder"""
        folder = task.params.get("folder")
        
        if not folder:
            return self._create_error_result(task, logs, start_time, "Missing folder parameter")
        
        try:
            if os.path.exists(folder):
                files = os.listdir(folder)
                logs.append(f"Found {len(files)} files in {folder}")
                
                for file in files:
                    logs.append(f"  • {file}")
                
                return ExecutionResult(
                    status=ActionStatus.SUCCESS.value,
                    task_id=task.task_id,
                    context=task.context,
                    action="verify_file",
                    details=f"Verified folder contents: {len(files)} files found",
                    logs=logs,
                    timestamp=datetime.now().isoformat(),
                    duration=time.time() - start_time,
                    metadata={"folder": folder, "files": files}
                )
            else:
                return self._create_error_result(task, logs, start_time, f"Folder not found: {folder}")
        
        except Exception as e:
            return self._create_error_result(task, logs, start_time, f"Failed to verify files: {e}")
    
    def _save_file(self, task, logs, start_time):
        """Save content to a text or JSON file"""
        file_path = task.params.get("file_path")
        content = task.params.get("content", "")
        
        if not file_path:
            return self._create_error_result(task, logs, start_time, "Missing file_path parameter")
        
        try:
            # Create directory if it doesn't exist
            directory = os.path.dirname(file_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
                logs.append(f"Created directory: {directory}")
            
            # Replace placeholders in content
            content = content.replace("{timestamp}", datetime.now().isoformat())
            content = content.replace("{url}", task.params.get("source_url", "N/A"))
            content = content.replace("{filename}", os.path.basename(file_path))
            
            # Write content to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            file_size = os.path.getsize(file_path)
            logs.append(f"File saved: {file_path}")
            logs.append(f"File size: {file_size} bytes")
            
            return ExecutionResult(
                status=ActionStatus.SUCCESS.value,
                task_id=task.task_id,
                context=task.context,
                action="save_file",
                details=f"File saved successfully: {file_path}",
                logs=logs,
                timestamp=datetime.now().isoformat(),
                duration=time.time() - start_time,
                metadata={
                    "file_path": file_path,
                    "file_size": file_size,
                    "content_length": len(content)
                }
            )
        
        except PermissionError:
            return self._create_error_result(task, logs, start_time, f"Permission denied: Cannot write to {file_path}")
        except Exception as e:
            return self._create_error_result(task, logs, start_time, f"Failed to save file: {e}")
    
    # ==================== LOGGING ACTIONS ====================
    
    def _log_completion(self, task, logs, start_time):
        """Log workflow completion"""
        workflow_id = task.params.get("workflow_id", "unknown")
        status = task.params.get("status", "completed")
        
        try:
            logs.append(f"Workflow {workflow_id} {status}")
            
            # Create completion log
            log_content = f"""
===========================================
WORKFLOW COMPLETION LOG
===========================================
Workflow ID: {workflow_id}
Status: {status}
Completed At: {datetime.now().isoformat()}
Task ID: {task.task_id}
===========================================
"""
            
            # Save to system log
            log_path = "C:\\Users\\Public\\Documents\\workflow_completions.log"
            
            try:
                with open(log_path, 'a', encoding='utf-8') as f:
                    f.write(log_content)
                logs.append(f"Completion logged to: {log_path}")
            except:
                logs.append("Could not write to completion log file")
            
            return ExecutionResult(
                status=ActionStatus.SUCCESS.value,
                task_id=task.task_id,
                context=task.context,
                action="log_completion",
                details=f"Workflow {workflow_id} completed",
                logs=logs,
                timestamp=datetime.now().isoformat(),
                duration=time.time() - start_time,
                metadata={"workflow_id": workflow_id, "status": status}
            )
        
        except Exception as e:
            return self._create_error_result(task, logs, start_time, f"Failed to log completion: {e}")
    
    # ==================== HELPER METHODS ====================
    
    def _create_error_result(self, task, logs, start_time, error):
        """Helper to create error result"""
        logs.append(error)
        return ExecutionResult(
            status=ActionStatus.FAILED.value,
            task_id=task.task_id,
            context=task.context,
            action="system_command",
            details=error,
            logs=logs,
            timestamp=datetime.now().isoformat(),
            duration=time.time() - start_time,
            error=error
        )