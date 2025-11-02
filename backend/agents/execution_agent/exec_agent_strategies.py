"""
Execution Strategies Module
Implements different execution strategies: Local, Web, System

Author: Accessibility AI Team
Version: 1.0.0
"""

import time
import platform
import subprocess
from datetime import datetime
from typing import List

from exec_agent_config import Config, ActionStatus
from exec_agent_models import ExecutionTask, ExecutionResult
from exec_agent_deps import (
    PYWINAUTO_AVAILABLE, SELENIUM_AVAILABLE,
    Application, webdriver, By, WebDriverWait, EC
)


class LocalStrategy:
    """Execute local Windows automation tasks"""
    
    def __init__(self, logger, vision_layer, action_layer, safety_layer):
        self.logger = logger
        self.vision = vision_layer
        self.action = action_layer
        self.safety = safety_layer
    
    def execute(self, task: ExecutionTask) -> ExecutionResult:
        """Execute local automation task"""
        start_time = time.time()
        logs = []
        
        try:
            action_type = task.params.get("action_type", "")
            
            if action_type == "open_app":
                return self._open_application(task, logs, start_time)
            
            elif action_type == "click_element":
                return self._click_element(task, logs, start_time)
            
            elif action_type == "type_text":
                return self._type_text(task, logs, start_time)
            
            elif action_type == "send_message":
                return self._send_message(task, logs, start_time)
            
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
    
    def _click_element(self, task: ExecutionTask, logs: List, start_time: float) -> ExecutionResult:
        """Click UI element with multi-strategy fallback"""
        element_desc = task.params.get("element", {})
        
        logs.append("Attempting to locate element")
        
        # Strategy 1: Try UIA
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
        
        # Strategy 2: Try OCR
        if element_desc.get("text"):
            logs.append("Falling back to OCR detection")
            vision_result = self.vision.detect_element_ocr(element_desc["text"])
            
            if vision_result.element_found and vision_result.confidence > Config.OCR_CONFIDENCE_THRESHOLD:
                logs.append(f"Element found via OCR (confidence: {vision_result.confidence:.2f})")
                if self.action.click(vision_result.coordinates):
                    logs.append("Click successful")
                    return self._create_success_result(task, logs, start_time, "Element clicked via OCR")
        
        # Strategy 3: Try template matching
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
    
    def _type_text(self, task: ExecutionTask, logs: List, start_time: float) -> ExecutionResult:
        """Type text into focused field"""
        text = task.params.get("text")
        
        if not text:
            return self._create_error_result(task, logs, start_time, "Missing text parameter")
        
        try:
            logs.append(f"Typing text: {text[:50]}...")
            
            if self.action.type_text(text):
                logs.append("Text typed successfully")
                return self._create_success_result(task, logs, start_time, "Text typed successfully")
            else:
                return self._create_error_result(task, logs, start_time, "Failed to type text")
        
        except Exception as e:
            return self._create_error_result(task, logs, start_time, f"Error typing text: {e}")
    
    def _send_message(self, task: ExecutionTask, logs: List, start_time: float) -> ExecutionResult:
        """Send message (Discord/WhatsApp example)"""
        platform_name = task.params.get("platform", "discord")
        server_name = task.params.get("server_name")
        channel_image = task.params.get("channel_image")
        message = task.params.get("message")
        
        try:
            logs.append(f"Opening {platform_name}")
            
            # Open Quick Switcher
            self.action.hotkey('ctrl', 'k')
            time.sleep(1)
            logs.append("Opened quick switcher")
            
            # Type server name
            self.action.type_text(server_name, interval=0.1)
            time.sleep(1)
            
            self.action.press_key('enter')
            time.sleep(3)
            logs.append(f"Entered server: {server_name}")
            
            # Click channel using image recognition
            if channel_image:
                vision_result = self.vision.detect_element_image(channel_image)
                
                if vision_result.element_found:
                    self.action.click(vision_result.coordinates)
                    time.sleep(2)
                    logs.append("Joined channel")
                else:
                    return self._create_error_result(task, logs, start_time, "Channel not found")
            
            # Send message
            self.action.press_key('tab')
            time.sleep(1)
            
            self.action.type_text(message, interval=0.05)
            self.action.press_key('enter')
            logs.append(f"Message sent: {message}")
            
            return self._create_success_result(task, logs, start_time, f"Message sent to {server_name}")
        
        except Exception as e:
            return self._create_error_result(task, logs, start_time, f"Failed to send message: {e}")
    
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


class WebStrategy:
    """Execute web automation tasks"""
    
    def __init__(self, logger, safety_layer):
        self.logger = logger
        self.safety = safety_layer
        self.driver = None
    
    def execute(self, task: ExecutionTask) -> ExecutionResult:
        """Execute web automation task"""
        start_time = time.time()
        logs = []
        
        try:
            if not SELENIUM_AVAILABLE:
                return self._create_error_result(task, logs, start_time, "Selenium not available")
            
            # Execute web-specific actions
            action_type = task.params.get("action_type", "")
            
            # Extract and web_search create their own drivers
            if action_type == "extract_web_content":
                return self._extract_web_content(task, logs, start_time)
            
            # Initialize browser for other actions (use Edge instead of Chrome)
            if not self.driver:
                try:
                    self.driver = webdriver.Edge()
                    logs.append("Edge browser opened")
                except Exception as e:
                    # Fallback to Chrome if Edge fails
                    try:
                        self.driver = webdriver.Chrome()
                        logs.append("Chrome browser opened (Edge unavailable)")
                    except Exception as e2:
                        return self._create_error_result(task, logs, start_time, f"Failed to open browser: {e2}")
            
            url = task.params.get("url")
            if url:
                self.driver.get(url)
                logs.append(f"Navigated to {url}")
            
            if action_type == "login":
                return self._login(task, logs, start_time)
            elif action_type == "download_file":
                return self._download_file(task, logs, start_time)
            elif action_type == "fill_form":
                return self._fill_form(task, logs, start_time)
            elif action_type == "web_search":
                return self._web_search(task, logs, start_time)
            else:
                return self._create_error_result(task, logs, start_time, f"Unknown web action: {action_type}")
        
        except Exception as e:
            self.logger.error(f"Web execution error: {e}")
            return self._create_error_result(task, logs, start_time, f"Web automation failed: {e}")
        
        finally:
            if self.driver:
                self.driver.quit()
                logs.append("Browser closed")
    
    def _login(self, task, logs, start_time):
        """Login to web application"""
        username = task.params.get("username")
        password = task.params.get("password")
        
        try:
            username_field = WebDriverWait(self.driver, Config.WEB_WAIT_TIMEOUT).until(
                EC.presence_of_element_located((By.NAME, "username"))
            )
            username_field.send_keys(username)
            logs.append("Username entered")
            
            password_field = self.driver.find_element(By.NAME, "password")
            password_field.send_keys(password)
            logs.append("Password entered")
            
            login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            login_button.click()
            logs.append("Login submitted")
            
            time.sleep(3)
            
            return self._create_success_result(task, logs, start_time, "Login successful")
        
        except Exception as e:
            return self._create_error_result(task, logs, start_time, f"Login failed: {e}")
    
    def _download_file(self, task, logs, start_time):
        """Download file from web"""
        file_link_text = task.params.get("file_link_text")
        
        try:
            download_link = WebDriverWait(self.driver, Config.WEB_WAIT_TIMEOUT).until(
                EC.presence_of_element_located((By.LINK_TEXT, file_link_text))
            )
            
            download_link.click()
            logs.append(f"Clicked download link: {file_link_text}")
            time.sleep(5)
            
            return self._create_success_result(task, logs, start_time, "File download initiated")
        
        except Exception as e:
            return self._create_error_result(task, logs, start_time, f"Download failed: {e}")
    
    def _fill_form(self, task, logs, start_time):
        """Fill web form"""
        form_data = task.params.get("form_data", {})
        
        try:
            for field_name, value in form_data.items():
                field = self.driver.find_element(By.NAME, field_name)
                field.send_keys(value)
                logs.append(f"Filled field: {field_name}")
            
            return self._create_success_result(task, logs, start_time, "Form filled successfully")
        
        except Exception as e:
            return self._create_error_result(task, logs, start_time, f"Form filling failed: {e}")
    
    def _web_search(self, task: ExecutionTask, logs: List, start_time: float) -> ExecutionResult:
        """Perform web search via browser"""
        search_query = task.params.get("search_query", "")
        search_engine = task.params.get("search_engine", "google")
        
        if not search_query:
            return self._create_error_result(task, logs, start_time, "Missing search_query parameter")
        
        try:
            logs.append(f"Searching for: {search_query}")
            
            # Wait for browser to be ready
            time.sleep(2)
            
            # Click address bar (Ctrl+L)
            self.driver.find_element(By.TAG_NAME, "body").send_keys('l') # Simulate Ctrl+L
            time.sleep(1)
            logs.append("Activated address bar")
            
            # Build search URL
            if search_engine == "google":
                search_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
            elif search_engine == "bing":
                search_url = f"https://www.bing.com/search?q={search_query.replace(' ', '+')}"
            else:
                search_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
            
            # Type search URL
            self.driver.find_element(By.TAG_NAME, "body").send_keys(search_url) # Simulate typing URL
            time.sleep(0.5)
            
            # Press Enter
            self.driver.find_element(By.TAG_NAME, "body").send_keys('enter') # Simulate Enter
            time.sleep(3)
            logs.append(f"Search completed for: {search_query}")
            
            return self._create_success_result(
                task, logs, start_time,
                f"Search completed: {search_query}"
            )
        
        except Exception as e:
            return self._create_error_result(task, logs, start_time, f"Web search failed: {e}")
    
    def _extract_web_content(self, task: ExecutionTask, logs: List, start_time: float) -> ExecutionResult:
        """Extract text from the first website after a search result (Selenium, Edge/Bing preferred)"""
        if not SELENIUM_AVAILABLE:
            return self._create_error_result(task, logs, start_time, "Selenium not available for extraction")
        
        search_engine = task.params.get("search_engine", "bing")
        search_query = task.params.get("search_query", "")
        driver = None
        
        try:
            # Create Edge driver (preferred)
            try:
                driver = webdriver.Edge()
                logs.append("Edge browser opened for content extraction")
            except Exception as e:
                # Fallback to Chrome if Edge fails
                try:
                    driver = webdriver.Chrome()
                    logs.append("Chrome browser opened for content extraction (Edge unavailable)")
                except Exception as e2:
                    return self._create_error_result(task, logs, start_time, f"Failed to open browser: {e2}")
            
            driver.implicitly_wait(10)
            logs.append(f"Searching for: {search_query}")
            
            # Build search URL (always use Bing for better automation compatibility)
            search_url = f"https://www.bing.com/search?q={search_query.replace(' ', '+')}"
            driver.get(search_url)
            logs.append(f"Opened search page: {search_url}")
            time.sleep(2)  # Wait for page to load
            
            # Find first organic result link
            try:
                first_result = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'li.b_algo a'))
                )
                first_url = first_result.get_attribute("href")
                logs.append(f"Navigating to first result: {first_url}")
                driver.get(first_url)
                time.sleep(2)  # Wait for content page to load
            except Exception as e:
                logs.append(f"Warning: Could not find first result link: {e}")
                # Try alternative selector
                try:
                    first_result = driver.find_element(By.CSS_SELECTOR, 'h2 a')
                    first_url = first_result.get_attribute("href")
                    logs.append(f"Found alternative result: {first_url}")
                    driver.get(first_url)
                    time.sleep(2)
                except Exception as e2:
                    return self._create_error_result(task, logs, start_time, f"Failed to find search result: {e2}")
            
            # Extract main text: collect visible paragraphs
            paragraphs = driver.find_elements(By.TAG_NAME, "p")
            text_content = "\n".join([p.text for p in paragraphs if p.text.strip()])
            
            # If no paragraphs found, try getting body text
            if not text_content or len(text_content) < 50:
                try:
                    body = driver.find_element(By.TAG_NAME, "body")
                    text_content = body.text
                    logs.append("Extracted content from body element")
                except:
                    pass
            
            if not text_content or len(text_content) < 10:
                text_content = f"Content extraction from {first_url} - Limited content available. Please check the source URL."
                logs.append("Warning: Minimal content extracted")
            
            logs.append(f"Extracted {len(text_content)} characters from first result.")
            
            return ExecutionResult(
                status=ActionStatus.SUCCESS.value,
                task_id=task.task_id,
                context=task.context,
                action=task.action_type,
                details=f"Extracted {len(text_content)} characters of web content.",
                logs=logs,
                timestamp=datetime.now().isoformat(),
                duration=time.time() - start_time,
                metadata={"web_content": text_content, "source_url": first_url}
            )
            
        except Exception as e:
            error_msg = f"Web content extraction failed: {e}"
            logs.append(f"Extraction error: {e}")
            import traceback
            logs.append(f"Traceback: {traceback.format_exc()}")
            return self._create_error_result(task, logs, start_time, error_msg)
        finally:
            # Always close the driver
            if driver:
                try:
                    driver.quit()
                    logs.append("Browser closed")
                except:
                    pass
    
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
    
    def _create_folder(self, task, logs, start_time):
        """Create folder on filesystem"""
        import os
        
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
        import os
        
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
        import os
        
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
            
            # Write content to file
            mode = 'w'
            encoding = 'utf-8'
            
            with open(file_path, mode, encoding=encoding) as f:
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
