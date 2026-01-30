# ============================================================================
# WEB CODE EXECUTION - RAG + PLAYWRIGHT INTEGRATION (FIXED)
# ============================================================================


import asyncio
import logging
import json
import os
import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

# ============================================================================
# EXECUTION STATUS & RESULT CLASSES
# ============================================================================

class ExecutionStatus(Enum):
    """Web execution status"""
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SECURITY_VIOLATION = "security_violation"

@dataclass
class WebExecutionConfig:
    """Configuration for web execution"""
    headless: bool = False
    timeout_seconds: int = 30
    screenshots_enabled: bool = True
    screenshot_dir: str = "web_screenshots"
    max_navigation_time: int = 10000  # milliseconds
    slow_mo: int = 100  # milliseconds between actions
    viewport_width: int = 1280
    viewport_height: int = 720
    enable_verification: bool = True  # ✅ NEW: Enable post-action verification
    enable_page_context: bool = True  # ✅ NEW: Enable DOM-aware context

@dataclass
class WebExecutionResult:
    """Result of web code execution"""
    validation_passed: bool
    security_passed: bool
    output: Optional[str] = None
    error: Optional[str] = None
    validation_errors: List[str] = field(default_factory=list)
    security_violations: List[str] = field(default_factory=list)
    page_url: Optional[str] = None
    page_title: Optional[str] = None
    extracted_data: Optional[Dict] = None
    screenshot_path: Optional[str] = None
    execution_time: float = 0.0
    verification_message: Optional[str] = None  # ✅ NEW: Verification details

# ============================================================================
# WEB EXECUTION PIPELINE - RAG + DOM AWARENESS
# ============================================================================

class WebExecutionPipeline:
    """Handles Playwright-based web automation using RAG with DOM awareness"""
    
    def __init__(self, config: WebExecutionConfig):
        self.config = config
        self.playwright = None
        self.browser = None
        self.context = None
        self.sessions = {}  # session_id -> page mapping
        self._rag_system = None  # Lazy-loaded RAG system
        self.shared_groq_client = None  # Shared Groq client from desktop RAG
        
        Path(self.config.screenshot_dir).mkdir(parents=True, exist_ok=True)
    
    async def initialize(self):
        """Initialize Playwright browser with anti-detection"""
        try:
            from playwright.async_api import async_playwright
            
            logger.info("Initializing Playwright with stealth mode...")
            
            self.playwright = await async_playwright().start()
            
            # ✅ FIX 4: ANTI-DETECTION LAUNCH ARGS
            self.browser = await self.playwright.chromium.launch(
                headless=self.config.headless,
                slow_mo=self.config.slow_mo,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-infobars',
                    '--window-size=1920,1080',
                    '--start-maximized'
                ]
            )
            
            # ✅ FIX 4: STEALTH CONTEXT
            self.context = await self.browser.new_context(
                viewport={'width': self.config.viewport_width, 'height': self.config.viewport_height},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='en-US',
                timezone_id='America/New_York',
                permissions=['geolocation'],
                geolocation={'longitude': -74.006, 'latitude': 40.7128},  # New York
                extra_http_headers={
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
                }
            )
            
            # ✅ FIX 4: INJECT ANTI-DETECTION SCRIPTS
            await self.context.add_init_script("""
                // Override navigator.webdriver
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // Mock plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                
                // Mock languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
                
                // Override chrome detection
                window.chrome = {
                    runtime: {}
                };
                
                // Mock permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            """)
            
            logger.info("✅ Playwright initialized with anti-detection measures")
            
        except Exception as e:
            logger.error(f"Failed to initialize Playwright: {e}")
            raise
    
    async def get_or_create_page(self, session_id: str):
        """Get existing page for session or create new one"""
        if session_id not in self.sessions or self.sessions[session_id].is_closed():
            page = await self.context.new_page()
            self.sessions[session_id] = page
            logger.info(f"Created new page for session {session_id}")
        
        return self.sessions[session_id]
    
    async def _initialize_rag_system(self):
        """Lazy initialize RAG system"""
        if self._rag_system is not None:
            return
        
        try:
            logger.info("Initializing Playwright RAG system...")
            
            from agents.execution_agent.RAG.web.code_generation import (
                PlaywrightRAGSystem,
                PlaywrightRAGConfig
            )
            
            rag_config = PlaywrightRAGConfig()
            
            # Use shared Groq client to avoid API key issues
            self._rag_system = PlaywrightRAGSystem(
                rag_config,
                llm_client=self.shared_groq_client
            )
            self._rag_system.initialize()
            
            logger.info("Playwright RAG system initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize RAG: {e}")
            raise
    
    async def execute_web_task(
        self,
        task: Dict[str, Any],
        session_id: str = "default"
    ) -> WebExecutionResult:
        """Execute a web automation task using RAG with DOM awareness"""
        
        start_time = datetime.now()
        task_id = task.get('task_id', 'unknown')
        
        logger.info(f"Executing web task {task_id}")
        
        try:
            page = await self.get_or_create_page(session_id)
            
            ai_prompt = task.get('ai_prompt', '')
            
            # Validation
            validation_errors = []
            if not ai_prompt:
                validation_errors.append("No ai_prompt provided")
            
            if validation_errors:
                return WebExecutionResult(
                    validation_passed=False,
                    security_passed=True,
                    validation_errors=validation_errors,
                    execution_time=(datetime.now() - start_time).total_seconds()
                )
            
            # ✅ NEW: Capture page state before execution
            url_before = page.url
            action_type = task.get('web_params', {}).get('action', 'unknown')
            
            # Generate code using RAG (now with DOM context)
            logger.info(f"Using RAG to generate code from: {ai_prompt}")
            
            try:
                generated_code = await self._generate_code_from_rag(ai_prompt, page, task)
            except Exception as e:
                logger.error(f"RAG generation failed: {e}")
                return WebExecutionResult(
                    validation_passed=False,
                    security_passed=True,
                    error=f"RAG code generation failed: {str(e)}",
                    execution_time=(datetime.now() - start_time).total_seconds()
                )
            
            # Security check
            security_result = self._security_check(generated_code)
            if not security_result['passed']:
                return WebExecutionResult(
                    validation_passed=False,
                    security_passed=False,
                    security_violations=security_result['violations'],
                    execution_time=(datetime.now() - start_time).total_seconds()
                )
            
            # Execute RAG-generated code
            logger.info(f"Executing RAG-generated Playwright code")
            result = await self._execute_generated_code(page, generated_code, task_id)
            
            # ✅ NEW: Post-action verification (if enabled and execution succeeded)
            verification_passed = True
            verification_message = None
            
            if self.config.enable_verification and result.get('success'):
                from agents.execution_agent.RAG.web.verifiers import verify_action
                
                verify_context = {
                    'url_before': url_before,
                    'text': task.get('web_params', {}).get('text'),
                    'task_id': task_id,
                    'extracted_data': result.get('extracted_data')
                }
                
                verification_passed, verification_message = await verify_action(
                    page, 
                    action_type, 
                    verify_context
                )
                
                if not verification_passed:
                    logger.error(f"❌ Verification failed: {verification_message}")
                    result['success'] = False
                    result['error'] = f"Action executed but verification failed: {verification_message}"
                else:
                    logger.info(f"✅ Verification passed: {verification_message}")
            
            # Get page info
            page_url = page.url
            page_title = await page.title()
            
            # Take screenshot if enabled
            screenshot_path = None
            if self.config.screenshots_enabled:
                screenshot_path = os.path.join(
                    self.config.screenshot_dir,
                    f"{task_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                )
                await page.screenshot(path=screenshot_path)
                logger.info(f"Screenshot saved: {screenshot_path}")
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return WebExecutionResult(
                validation_passed=result.get('success', False),
                security_passed=True,
                output=result.get('output', ''),
                error=result.get('error'),
                page_url=page_url,
                page_title=page_title,
                extracted_data=result.get('extracted_data'),
                screenshot_path=screenshot_path,
                execution_time=execution_time,
                verification_message=verification_message
            )
            
        except asyncio.TimeoutError:
            logger.error(f"Task {task_id} timed out")
            return WebExecutionResult(
                validation_passed=False,
                security_passed=True,
                error=f"Timeout after {self.config.timeout_seconds}s",
                execution_time=(datetime.now() - start_time).total_seconds()
            )
        
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            import traceback
            return WebExecutionResult(
                validation_passed=False,
                security_passed=True,
                error=f"{str(e)}\n{traceback.format_exc()}",
                execution_time=(datetime.now() - start_time).total_seconds()
            )
    
    async def _generate_code_from_rag(
        self, 
        ai_prompt: str, 
        page, 
        task: Dict[str, Any]
    ) -> str:
        """Generate Playwright code using RAG with DOM-aware context"""
        
        await self._initialize_rag_system()
        
        # ✅ NEW: Build enhanced prompt with page context
        if self.config.enable_page_context:
            from agents.execution_agent.RAG.web.page_inspector import build_rag_context
            
            try:
                enhanced_prompt = await build_rag_context(page, ai_prompt)
                logger.info(f"🔍 Using DOM-aware RAG context")
            except Exception as e:
                logger.warning(f"⚠️ Could not build page context: {e}")
                enhanced_prompt = ai_prompt
        else:
            enhanced_prompt = ai_prompt
        
        logger.info(f"RAG Query: {ai_prompt}")
        
        try:
            rag_result = self._rag_system.generate_code(
                enhanced_prompt,
                include_explanation=False
            )
            
            generated_code = rag_result.get('code', '')
            
            if not generated_code:
                raise ValueError("RAG system returned empty code")
            
            logger.info(f"RAG generated {len(generated_code)} chars of Playwright code")
            logger.debug(f"Code preview:\n{generated_code[:300]}...")
            
            return generated_code
            
        except Exception as e:
            logger.error(f"RAG code generation failed: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    async def _execute_generated_code(
        self,
        page,
        code: str,
        task_id: str
    ) -> Dict[str, Any]:
        """Execute RAG-generated Playwright code with proper failure detection"""
        
        logger.info(f"Executing generated code for task {task_id}")
        
        try:
            logger.debug(f"Original code length: {len(code)} chars")
            
            # ==============================
            # CLEAN CODE
            # ==============================
            # Remove asyncio.run() patterns that crash in async context
            code = re.sub(r'\nasyncio\.run\(main\(\)\)\s*$', '', code, flags=re.MULTILINE)
            code = re.sub(
                r'if\s+__name__\s*==\s*["\']__main__["\']\s*:\s*\n?\s*asyncio\.run\(main\(\)\)',
                '',
                code,
                flags=re.MULTILINE | re.DOTALL
            )
            code = re.sub(r'asyncio\.run\([^)]+\)', '', code)
            
            # Replace close calls with 'pass' to keep browser open
            code = re.sub(r'await\s+browser\.close\(\)', 'pass  # Browser kept open', code)
            code = re.sub(r'browser\.close\(\)', 'pass  # Browser kept open', code)
            code = re.sub(r'await\s+context\.close\(\)', 'pass  # Context kept open', code)
            code = re.sub(r'context\.close\(\)', 'pass  # Context kept open', code)
            code = re.sub(r'await\s+playwright\.stop\(\)', 'pass  # Playwright kept running', code)
            code = re.sub(r'finally:\s*\n\s*\n', 'finally:\n        pass  # Keep browser open\n', code)
            
            logger.debug(f"Cleaned code length: {len(code)} chars")
            
            # ==============================
            # WRAP IN ASYNC FUNCTION WITH OUTPUT CAPTURE
            # ==============================
            def _indent(text, spaces=4):
                """Indent text by specified number of spaces"""
                return '\n'.join((' ' * spaces) + line if line.strip() else line for line in text.splitlines())
            
            wrapped_code = f"""
import sys
from io import StringIO

# Capture stdout
_stdout_capture = StringIO()
_original_stdout = sys.stdout

async def __rag_step__(page):
    # Redirect stdout to capture
    sys.stdout = _stdout_capture
    
    try:
{_indent(code, 8)}
    finally:
        # Restore stdout
        sys.stdout = _original_stdout
"""
            
            logger.debug(f"Wrapped code preview:\n{wrapped_code[:300]}...")
            
            # ==============================
            # EXECUTE WITH OUTPUT CAPTURE
            # ==============================
            exec_namespace = {
                'page': page,
                'asyncio': asyncio,
                '__result__': None,
                '__stdout__': ''
            }
            
            # Define __rag_step__ in namespace
            exec(wrapped_code, exec_namespace)
            
            # Await the wrapped function
            logger.info(f"Executing wrapped RAG code...")
            result_data = await exec_namespace['__rag_step__'](page)
            
            # Get captured stdout
            stdout_content = exec_namespace['_stdout_capture'].getvalue()
            exec_namespace['__stdout__'] = stdout_content
            
            # If RAG code sets __result__, use that instead
            if exec_namespace.get('__result__') is not None:
                result_data = exec_namespace['__result__']
            
            # ✅ CRITICAL FIX: Parse stdout for success/failure
            success, message = self._parse_execution_output(stdout_content)
            
            if not success:
                logger.error(f"❌ Code reported failure: {message}")
                return {
                    'success': False,
                    'error': message,
                    'output': stdout_content
                }
            
            logger.info(f"✅ Code executed successfully")
            
            return {
                'success': True,
                'output': stdout_content,
                'extracted_data': result_data
            }
            
        except Exception as e:
            logger.error(f"Code execution failed: {e}")
            import traceback
            logger.debug(f"Traceback:\n{traceback.format_exc()}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _parse_execution_output(self, stdout: str) -> tuple[bool, str]:
        """
        ✅ NEW: Parse stdout to determine actual success/failure
        
        Returns:
            (success: bool, message: str)
        """
        
        # Check for explicit failure from Playwright
        if 'FAILED:' in stdout:
            # Extract failure message
            failure_msg = stdout.split('FAILED:')[1].split('\n')[0].strip()
            return False, f"Playwright error: {failure_msg}"
        
        # Check for Playwright timeout errors
        if 'Timeout' in stdout and 'exceeded' in stdout:
            return False, "Playwright timeout exceeded"
        
        # Check for element not found errors
        if 'not found' in stdout.lower() or 'cannot find' in stdout.lower():
            return False, "Required element not found on page"
        
        # Check for success indicator
        if 'EXECUTION_SUCCESS' in stdout:
            return True, "Execution successful"
        
        # If we have output but no clear success marker
        if len(stdout.strip()) > 0:
            # Assume success if there's output and no failure indicators
            return True, "Code executed (no explicit success marker)"
        
        # Empty output - probably failed
        return False, "No output generated (execution may have failed)"
    
    def _security_check(self, code: str) -> Dict[str, Any]:
        """Basic security validation"""
        
        violations = []
        
        dangerous_patterns = [
            'eval(',
            '__import__',
            'os.system',
            'subprocess',
            'rm -rf',
            'del ',
        ]
        
        for pattern in dangerous_patterns:
            if pattern in code:
                violations.append(f"Dangerous pattern detected: {pattern}")
        
        if 'file://' in code:
            violations.append("File system access not allowed")
        
        suspicious_domains = ['attacker.com', 'malicious.com']
        for domain in suspicious_domains:
            if domain in code:
                violations.append(f"Suspicious domain detected: {domain}")
        
        return {
            'passed': len(violations) == 0,
            'violations': violations
        }
    
    async def cleanup(self):
        """Clean up browser resources"""
        logger.info("Cleaning up Playwright resources...")
        
        try:
            for session_id, page in self.sessions.items():
                if not page.is_closed():
                    await page.close()
            
            if self.context:
                await self.context.close()
            
            if self.browser:
                await self.browser.close()
            
            if self.playwright:
                await self.playwright.stop()
            
            logger.info("Playwright cleanup complete")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

# ============================================================================
# TASK MODELS
# ============================================================================

class ActionTask:
    """Task format from coordinator agent"""
    def __init__(
        self,
        task_id: str,
        ai_prompt: str,
        device: str,
        context: str,
        target_agent: str,
        web_params: Optional[Dict[str, Any]] = None,
        extra_params: Optional[Dict[str, Any]] = None,
        depends_on: Optional[str] = None
    ):
        self.task_id = task_id
        self.ai_prompt = ai_prompt
        self.device = device
        self.context = context
        self.target_agent = target_agent
        self.web_params = web_params or {}
        self.extra_params = extra_params or {}
        self.depends_on = depends_on
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ActionTask':
        return cls(
            task_id=data.get('task_id', ''),
            ai_prompt=data.get('ai_prompt', ''),
            device=data.get('device', 'desktop'),
            context=data.get('context', 'web'),
            target_agent=data.get('target_agent', 'action'),
            web_params=data.get('web_params', {}),
            extra_params=data.get('extra_params', {}),
            depends_on=data.get('depends_on')
        )
    
    def dict(self) -> Dict[str, Any]:
        return {
            'task_id': self.task_id,
            'ai_prompt': self.ai_prompt,
            'device': self.device,
            'context': self.context,
            'target_agent': self.target_agent,
            'web_params': self.web_params,
            'extra_params': self.extra_params,
            'depends_on': self.depends_on
        }

class TaskResult:
    """Result format for coordinator agent"""
    def __init__(
        self,
        task_id: str,
        status: str,
        content: Optional[str] = None,
        error: Optional[str] = None,
        extracted_data: Optional[Dict] = None,
        screenshot: Optional[str] = None
    ):
        self.task_id = task_id
        self.status = status
        self.content = content
        self.error = error
        self.extracted_data = extracted_data
        self.screenshot = screenshot
    
    def dict(self) -> Dict[str, Any]:
        return {
            'task_id': self.task_id,
            'status': self.status,
            'content': self.content,
            'error': self.error,
            'extracted_data': self.extracted_data,
            'screenshot': self.screenshot
        }

# ============================================================================
# RAG TASK ADAPTER
# ============================================================================

class WebRAGTaskAdapter:
    """Adapts coordinator ActionTask to web execution requirements"""
    
    @staticmethod
    def execution_result_to_task_result(
        task: ActionTask,
        execution_result: WebExecutionResult
    ) -> TaskResult:
        
        if execution_result.validation_passed and execution_result.security_passed:
            status = "success"
            content = execution_result.output
            if execution_result.verification_message:
                content = f"{content}\nVerification: {execution_result.verification_message}"
            error = None
        else:
            status = "failed"
            content = None
            errors = []
            if execution_result.validation_errors:
                errors.extend(execution_result.validation_errors)
            if execution_result.security_violations:
                errors.extend(execution_result.security_violations)
            if execution_result.error:
                errors.append(f"error: {execution_result.error[:200]}")
            error = " | ".join(errors)
        
        return TaskResult(
            task_id=task.task_id,
            status=status,
            content=content,
            error=error,
            extracted_data=execution_result.extracted_data,
            screenshot=execution_result.screenshot_path
        )

# ============================================================================
# COORDINATOR WEB BRIDGE
# ============================================================================

class CoordinatorWebBridge:
    """Bridge between Coordinator Agent and Web Execution System"""
    
    def __init__(self, web_pipeline: WebExecutionPipeline):
        self.web = web_pipeline
        self.adapter = WebRAGTaskAdapter()
    
    async def execute_web_action_task(
        self,
        task: ActionTask,
        session_id: str = "default",
        max_retries: int = 2
    ) -> TaskResult:
        """Execute a single web ActionTask using RAG + Playwright pipeline"""
        
        logger.info(f"Processing web task {task.task_id}: {task.ai_prompt[:50]}...")
        
        if task.target_agent != "action":
            logger.warning(f"Task {task.task_id} is not an action task")
            return TaskResult(
                task_id=task.task_id,
                status="failed",
                error="Not an action task - should be handled by reasoning agent"
            )
        
        attempt = 0
        
        while attempt < max_retries:
            attempt += 1
            logger.info(f"Attempt {attempt}/{max_retries} for task {task.task_id}")
            
            try:
                task_dict = {
                    'task_id': task.task_id,
                    'ai_prompt': task.ai_prompt,
                    'web_params': task.web_params
                }
                
                exec_result = await self.web.execute_web_task(task_dict, session_id)
                
                if exec_result.validation_passed and exec_result.security_passed:
                    logger.info(f"Task {task.task_id} completed successfully")
                    return self.adapter.execution_result_to_task_result(task, exec_result)
                
                logger.warning(f"Execution failed (attempt {attempt})")
                
            except Exception as e:
                logger.error(f"Exception during web execution: {e}")
                if attempt == max_retries:
                    break
        
        logger.error(f"Task {task.task_id} failed after {max_retries} attempts")
        return TaskResult(
            task_id=task.task_id,
            status="failed",
            error=f"Failed after {max_retries} attempts"
        )

# ============================================================================
# WEB EXECUTION AGENT INTEGRATION
# ============================================================================

async def start_web_execution_agent_with_rag(broker_instance, rag_system, web_pipeline):
    """Start web execution agent that handles web ActionTasks from coordinator"""
    
    bridge = CoordinatorWebBridge(web_pipeline)
    
    async def handle_web_execution_request(message):
        try:
            task_data = message.payload
            task = ActionTask.from_dict(task_data)
            
            logger.info(f"Web execution agent received task {task.task_id}")
            
            result = await bridge.execute_web_action_task(
                task=task,
                session_id=message.session_id,
                max_retries=2
            )
            
            from agents.utils.protocol import AgentMessage, MessageType, AgentType, Channels
            
            response_msg = AgentMessage(
                message_type=MessageType.EXECUTION_RESPONSE,
                sender=AgentType.EXECUTION,
                receiver=AgentType.COORDINATOR,
                session_id=message.session_id,
                task_id=task.task_id,
                response_to=message.message_id,
                payload=result.dict()
            )
            
            await broker_instance.publish(Channels.EXECUTION_TO_COORDINATOR, response_msg)
            logger.info(f"Sent result for task {task.task_id}: {result.status}")
            
        except Exception as e:
            logger.error(f"Error processing web execution request: {e}")
            
            error_result = TaskResult(
                task_id=message.task_id or "unknown",
                status="failed",
                error=str(e)
            )
            
            from agents.utils.protocol import AgentMessage, MessageType, AgentType, Channels
            
            error_msg = AgentMessage(
                message_type=MessageType.EXECUTION_RESPONSE,
                sender=AgentType.EXECUTION,
                receiver=AgentType.COORDINATOR,
                session_id=message.session_id,
                task_id=message.task_id,
                response_to=message.message_id,
                payload=error_result.dict()
            )
            
            await broker_instance.publish(Channels.EXECUTION_TO_COORDINATOR, error_msg)
    
    from agents.utils.protocol import Channels
    broker_instance.subscribe(Channels.COORDINATOR_TO_EXECUTION, handle_web_execution_request)
    
    logger.info("Web Execution Agent started with RAG + Playwright + DOM awareness")
    
    while True:
        await asyncio.sleep(1)

async def initialize_web_execution_agent_for_server(broker_instance):
    """Server-compatible initialization for web execution agent with RAG system"""
    
    from dotenv import load_dotenv
    load_dotenv()
    
    if hasattr(broker_instance, '_web_rag_execution_subscribed'):
        logger.warning("Web RAG Execution agent already subscribed, skipping")
        return
    broker_instance._web_rag_execution_subscribed = True
    
    try:
        from agents.execution_agent.RAG.web.code_generation import RAGSystem, RAGConfig
        
        try:
            logger.info("Initializing RAG system for Playwright...")
            rag_config = RAGConfig(library_name="playwright")
            rag_system = RAGSystem(rag_config)
            rag_system.initialize()
            logger.info("Playwright RAG system ready")
        except Exception as e:
            logger.error(f"Failed to initialize Playwright RAG: {e}")
            raise
        
        try:
            logger.info("Initializing Playwright web pipeline...")
            
            web_config = WebExecutionConfig(
                headless=False,
                timeout_seconds=30,
                enable_verification=True,  # ✅ Enable verification
                enable_page_context=True   # ✅ Enable DOM awareness
            )
            web_pipeline = WebExecutionPipeline(web_config)
            await web_pipeline.initialize()
            
            logger.info("Playwright web pipeline ready with verification enabled")
            
        except Exception as e:
            logger.error(f"Web pipeline initialization error: {e}")
            raise
        
        logger.info("Starting web execution agent with RAG + Playwright + Verification...")
        await start_web_execution_agent_with_rag(broker_instance, rag_system, web_pipeline)
    
    except Exception as e:
        logger.error(f"Failed to initialize web execution agent: {e}")
        raise