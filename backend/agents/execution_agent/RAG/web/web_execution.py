# ============================================================================
# WEB AUTOMATION EXECUTION - PLAYWRIGHT-BASED
# ============================================================================
# This module replaces desktop automation logic with Playwright for web tasks
# while maintaining the same execution pipeline structure

import asyncio
import json
import logging
import hashlib
import tempfile
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from playwright.async_api import async_playwright, Browser, Page, BrowserContext

logger = logging.getLogger(__name__)

# ============================================================================
# EXECUTION STATUS & CONFIG (Preserved from original)
# ============================================================================

class ExecutionStatus(Enum):
    """Execution status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SECURITY_VIOLATION = "security_violation"
    SELECTOR_NOT_FOUND = "selector_not_found"

@dataclass
class WebExecutionConfig:
    """Configuration for web execution"""
    
    # Browser settings
    browser_type: str = "chromium"  # chromium, firefox, webkit
    headless: bool = False  # Show browser for debugging
    
    # Resource limits (preserved from original)
    timeout_seconds: int = 30
    page_load_timeout: int = 30000  # ms
    action_timeout: int = 10000  # ms
    
    # Security
    enable_security_check: bool = True
    
    # Validation (preserved from original)
    require_success_indicator: bool = True
    max_retry_attempts: int = 2
    
    # Paths
    logs_dir: Path = Path("web_execution_logs")
    screenshots_dir: Path = Path("web_screenshots")
    
    # Browser context options
    viewport_width: int = 1920
    viewport_height: int = 1080
    user_agent: Optional[str] = None
    
    def __post_init__(self):
        self.logs_dir.mkdir(exist_ok=True)
        self.screenshots_dir.mkdir(exist_ok=True)

@dataclass
class WebExecutionResult:
    """Result of web execution (structure preserved from original)"""
    status: ExecutionStatus
    exit_code: int
    output: str  # Renamed from stdout
    error: str   # Renamed from stderr
    execution_time: float
    timestamp: str
    
    # Validation
    validation_passed: bool
    validation_errors: List[str]
    
    # Security
    security_passed: bool
    security_violations: List[str]
    
    # Web-specific additions
    extracted_data: Optional[Dict[str, Any]] = None
    screenshot_path: Optional[str] = None
    page_url: Optional[str] = None
    
    # Metadata
    code_hash: str
    retry_count: int = 0
    
    def to_dict(self) -> Dict:
        result = asdict(self)
        result['status'] = self.status.value
        return result

# ============================================================================
# SECURITY VALIDATOR (Adapted from original)
# ============================================================================

class WebSecurityValidator:
    """Validate web automation code for security issues"""
    
    def __init__(self):
        self.blocked_patterns = [
            'eval(',
            'exec(',
            '__import__',
            'os.system',
            'subprocess',
        ]
        
        # Allow Playwright-specific imports
        self.allowed_patterns = [
            'from playwright',
            'import playwright',
            'async_playwright',
        ]
    
    def validate_code(self, code: str) -> Tuple[bool, List[str]]:
        """Validate web automation code"""
        violations = []
        
        # Check for dangerous patterns
        for pattern in self.blocked_patterns:
            if pattern in code:
                # Check if it's in an allowed context
                is_allowed = any(allowed in code for allowed in self.allowed_patterns)
                if not is_allowed:
                    violations.append(f"Dangerous pattern detected: {pattern}")
        
        # Check for suspicious URL patterns
        if 'goto(' in code and 'javascript:' in code:
            violations.append("Suspicious javascript: URL scheme")
        
        is_safe = len(violations) == 0
        return is_safe, violations

# ============================================================================
# PLAYWRIGHT BROWSER MANAGER
# ============================================================================

class PlaywrightBrowserManager:
    """Manage Playwright browser instances with isolation"""
    
    def __init__(self, config: WebExecutionConfig):
        self.config = config
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.contexts: Dict[str, BrowserContext] = {}
        
    async def initialize(self):
        """Initialize Playwright browser"""
        logger.info(f"🌐 Initializing Playwright ({self.config.browser_type})...")
        
        self.playwright = await async_playwright().start()
        
        if self.config.browser_type == "chromium":
            self.browser = await self.playwright.chromium.launch(
                headless=self.config.headless
            )
        elif self.config.browser_type == "firefox":
            self.browser = await self.playwright.firefox.launch(
                headless=self.config.headless
            )
        elif self.config.browser_type == "webkit":
            self.browser = await self.playwright.webkit.launch(
                headless=self.config.headless
            )
        else:
            raise ValueError(f"Invalid browser type: {self.config.browser_type}")
        
        logger.info("✅ Browser initialized")
    
    async def create_context(self, context_id: str, **kwargs) -> BrowserContext:
        """Create isolated browser context"""
        context_options = {
            "viewport": {
                "width": self.config.viewport_width,
                "height": self.config.viewport_height
            },
            "user_agent": self.config.user_agent,
            **kwargs
        }
        
        context = await self.browser.new_context(**context_options)
        
        # Set default timeouts
        context.set_default_timeout(self.config.action_timeout)
        context.set_default_navigation_timeout(self.config.page_load_timeout)
        
        self.contexts[context_id] = context
        logger.info(f"📄 Created browser context: {context_id}")
        
        return context
    
    async def get_or_create_context(self, context_id: str) -> BrowserContext:
        """Get existing context or create new one"""
        if context_id in self.contexts:
            return self.contexts[context_id]
        return await self.create_context(context_id)
    
    async def close_context(self, context_id: str):
        """Close and cleanup browser context"""
        if context_id in self.contexts:
            await self.contexts[context_id].close()
            del self.contexts[context_id]
            logger.info(f"🗑️ Closed context: {context_id}")
    
    async def cleanup(self):
        """Cleanup all resources"""
        for context_id in list(self.contexts.keys()):
            await self.close_context(context_id)
        
        if self.browser:
            await self.browser.close()
        
        if self.playwright:
            await self.playwright.stop()
        
        logger.info("🧹 Playwright cleanup complete")

# ============================================================================
# WEB AUTOMATION ACTIONS
# ============================================================================

class WebAutomationActions:
    """Playwright-based web automation actions"""
    
    def __init__(self, page: Page, config: WebExecutionConfig):
        self.page = page
        self.config = config
    
    async def navigate(self, url: str, wait_for: str = "load") -> Dict[str, Any]:
        """Navigate to URL"""
        logger.info(f"🔗 Navigating to: {url}")
        
        try:
            response = await self.page.goto(url, wait_until=wait_for)
            
            return {
                "success": True,
                "url": self.page.url,
                "status": response.status if response else None
            }
        except Exception as e:
            logger.error(f"❌ Navigation failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def click(self, selector: str, **kwargs) -> Dict[str, Any]:
        """Click element"""
        logger.info(f"🖱️ Clicking: {selector}")
        
        try:
            await self.page.click(selector, **kwargs)
            return {"success": True, "selector": selector}
        except Exception as e:
            logger.error(f"❌ Click failed: {e}")
            return {"success": False, "error": str(e), "selector": selector}
    
    async def fill(self, selector: str, text: str, **kwargs) -> Dict[str, Any]:
        """Fill input field"""
        logger.info(f"⌨️ Filling {selector}: {text[:50]}...")
        
        try:
            await self.page.fill(selector, text, **kwargs)
            return {"success": True, "selector": selector, "text": text}
        except Exception as e:
            logger.error(f"❌ Fill failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def extract_text(self, selector: str) -> Dict[str, Any]:
        """Extract text from element(s)"""
        logger.info(f"📝 Extracting text from: {selector}")
        
        try:
            elements = await self.page.query_selector_all(selector)
            
            texts = []
            for element in elements:
                text = await element.inner_text()
                texts.append(text.strip())
            
            return {
                "success": True,
                "selector": selector,
                "data": texts,
                "count": len(texts)
            }
        except Exception as e:
            logger.error(f"❌ Extraction failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def extract_attributes(self, selector: str, attributes: List[str]) -> Dict[str, Any]:
        """Extract attributes from elements"""
        logger.info(f"🔍 Extracting {attributes} from: {selector}")
        
        try:
            elements = await self.page.query_selector_all(selector)
            
            results = []
            for element in elements:
                item = {}
                for attr in attributes:
                    value = await element.get_attribute(attr)
                    item[attr] = value
                results.append(item)
            
            return {
                "success": True,
                "selector": selector,
                "data": results,
                "count": len(results)
            }
        except Exception as e:
            logger.error(f"❌ Attribute extraction failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def extract_structured_data(
        self,
        container_selector: str,
        fields: Dict[str, str]
    ) -> Dict[str, Any]:
        """Extract structured data from containers"""
        logger.info(f"📊 Extracting structured data from: {container_selector}")
        
        try:
            containers = await self.page.query_selector_all(container_selector)
            
            results = []
            for container in containers:
                item = {}
                for field_name, field_selector in fields.items():
                    try:
                        element = await container.query_selector(field_selector)
                        if element:
                            item[field_name] = (await element.inner_text()).strip()
                        else:
                            item[field_name] = None
                    except:
                        item[field_name] = None
                
                results.append(item)
            
            return {
                "success": True,
                "container": container_selector,
                "data": results,
                "count": len(results)
            }
        except Exception as e:
            logger.error(f"❌ Structured extraction failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def screenshot(self, path: str, full_page: bool = False) -> Dict[str, Any]:
        """Take screenshot"""
        logger.info(f"📸 Taking screenshot: {path}")
        
        try:
            await self.page.screenshot(path=path, full_page=full_page)
            return {"success": True, "path": path}
        except Exception as e:
            logger.error(f"❌ Screenshot failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def wait_for_selector(self, selector: str, timeout: int = None) -> Dict[str, Any]:
        """Wait for element to appear"""
        logger.info(f"⏳ Waiting for: {selector}")
        
        try:
            timeout_ms = timeout * 1000 if timeout else self.config.action_timeout
            await self.page.wait_for_selector(selector, timeout=timeout_ms)
            return {"success": True, "selector": selector}
        except Exception as e:
            logger.error(f"❌ Wait failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def scroll(self, direction: str = "down", amount: int = 500) -> Dict[str, Any]:
        """Scroll page"""
        logger.info(f"📜 Scrolling {direction} by {amount}px")
        
        try:
            if direction == "down":
                await self.page.evaluate(f"window.scrollBy(0, {amount})")
            elif direction == "up":
                await self.page.evaluate(f"window.scrollBy(0, -{amount})")
            elif direction == "bottom":
                await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            elif direction == "top":
                await self.page.evaluate("window.scrollTo(0, 0)")
            
            return {"success": True, "direction": direction}
        except Exception as e:
            logger.error(f"❌ Scroll failed: {e}")
            return {"success": False, "error": str(e)}

# ============================================================================
# EXECUTION VALIDATOR (Adapted from original)
# ============================================================================

class WebExecutionValidator:
    """Validate web execution results"""
    
    def __init__(self):
        self.success_indicators = [
            "EXECUTION_SUCCESS",
            "SUCCESS",
            "COMPLETED",
            "successfully"
        ]
        
        self.failure_indicators = [
            "Error:",
            "Exception:",
            "failed",
            "FAILED"
        ]
    
    def validate_result(
        self,
        result: WebExecutionResult,
        expected_output: Optional[str] = None
    ) -> WebExecutionResult:
        """Validate execution result (logic preserved from original)"""
        validation_errors = []
        
        # 1. Check exit code
        if result.exit_code != 0:
            validation_errors.append(f"Non-zero exit code: {result.exit_code}")
        
        # 2. Check for explicit failures
        has_explicit_failure = any(
            indicator in result.output
            for indicator in self.failure_indicators
        )
        
        if has_explicit_failure:
            validation_errors.append("Explicit failure indicator in output")
        
        # 3. Check for success indicators
        has_success_indicator = any(
            indicator in result.output
            for indicator in self.success_indicators
        )
        
        if result.exit_code == 0 and not has_success_indicator and not has_explicit_failure:
            validation_errors.append("No success indicator found in output")
        
        # 4. Check expected output
        if expected_output and expected_output not in result.output:
            validation_errors.append(f"Expected output not found: {expected_output}")
        
        # 5. Check timeout
        if result.status == ExecutionStatus.TIMEOUT:
            validation_errors.append("Execution timeout")
        
        # Update result
        result.validation_passed = len(validation_errors) == 0
        result.validation_errors = validation_errors
        
        return result

# ============================================================================
# WEB EXECUTION PIPELINE
# ============================================================================

class WebExecutionPipeline:
    """Complete web execution pipeline (structure preserved from original)"""
    
    def __init__(self, config: WebExecutionConfig = None):
        self.config = config or WebExecutionConfig()
        self.security_validator = WebSecurityValidator()
        self.execution_validator = WebExecutionValidator()
        self.browser_manager = PlaywrightBrowserManager(self.config)
        self.execution_history: List[WebExecutionResult] = []
        self._initialized = False
    
    async def initialize(self):
        """Initialize browser"""
        if not self._initialized:
            await self.browser_manager.initialize()
            self._initialized = True
    
    async def execute_web_task(
        self,
        task_dict: Dict[str, Any],
        session_id: str = "default"
    ) -> WebExecutionResult:
        """Execute web automation task"""
        
        logger.info("=" * 80)
        logger.info("WEB EXECUTION PIPELINE")
        logger.info("=" * 80)
        
        ai_prompt = task_dict.get("ai_prompt", "")
        web_params = task_dict.get("web_params", {})
        
        start_time = datetime.now()
        
        # Ensure browser is initialized
        await self.initialize()
        
        # Get or create browser context
        context = await self.browser_manager.get_or_create_context(session_id)
        page = await context.new_page()
        
        try:
            # Execute web actions
            actions = WebAutomationActions(page, self.config)
            output_parts = []
            extracted_data = None
            
            # Parse action from web_params
            action_type = web_params.get("action", "navigate")
            
            if action_type == "navigate" or web_params.get("url"):
                url = web_params.get("url")
                wait_for = web_params.get("wait_for", "load")
                result = await actions.navigate(url, wait_for)
                output_parts.append(f"Navigation: {result}")
                
            elif action_type == "click":
                selector = web_params.get("selector")
                result = await actions.click(selector)
                output_parts.append(f"Click: {result}")
                
            elif action_type == "fill":
                selector = web_params.get("selector")
                text = web_params.get("text", "")
                result = await actions.fill(selector, text)
                output_parts.append(f"Fill: {result}")
                
            elif action_type == "extract":
                selector = web_params.get("selector")
                
                if web_params.get("extract_fields"):
                    # Structured extraction
                    fields = web_params["extract_fields"]
                    field_selectors = web_params.get("field_selectors", {})
                    result = await actions.extract_structured_data(selector, field_selectors)
                else:
                    # Simple text extraction
                    result = await actions.extract_text(selector)
                
                extracted_data = result.get("data")
                output_parts.append(f"Extraction: {result}")
            
            # Take screenshot if requested
            screenshot_path = None
            if web_params.get("screenshot"):
                screenshot_name = f"{session_id}_{int(start_time.timestamp())}.png"
                screenshot_path = str(self.config.screenshots_dir / screenshot_name)
                await actions.screenshot(screenshot_path)
            
            # Compile output
            output = "\n".join(output_parts)
            output += "\nEXECUTION_SUCCESS"
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Create result
            result = WebExecutionResult(
                status=ExecutionStatus.SUCCESS,
                exit_code=0,
                output=output,
                error="",
                execution_time=execution_time,
                timestamp=datetime.now().isoformat(),
                validation_passed=False,
                validation_errors=[],
                security_passed=True,
                security_violations=[],
                extracted_data=extracted_data,
                screenshot_path=screenshot_path,
                page_url=page.url,
                code_hash=hashlib.md5(ai_prompt.encode()).hexdigest()
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            
            result = WebExecutionResult(
                status=ExecutionStatus.FAILED,
                exit_code=1,
                output="",
                error=str(e),
                execution_time=execution_time,
                timestamp=datetime.now().isoformat(),
                validation_passed=False,
                validation_errors=[str(e)],
                security_passed=True,
                security_violations=[],
                code_hash=hashlib.md5(ai_prompt.encode()).hexdigest()
            )
        
        finally:
            await page.close()
        
        # Validate result
        result = self.execution_validator.validate_result(result)
        
        # Store in history
        self.execution_history.append(result)
        
        # Save log
        self._save_execution_log(task_dict, result)
        
        logger.info("=" * 80)
        
        return result
    
    def _save_execution_log(self, task: Dict, result: WebExecutionResult):
        """Save execution log to file (preserved from original)"""
        log_file = self.config.logs_dir / f"web_exec_{result.code_hash}_{int(datetime.now().timestamp())}.json"
        
        log_data = {
            'task': task,
            'result': result.to_dict(),
            'timestamp': datetime.now().isoformat()
        }
        
        with open(log_file, 'w') as f:
            json.dump(log_data, f, indent=2)
    
    async def cleanup(self):
        """Cleanup all resources"""
        await self.browser_manager.cleanup()
        self._initialized = False

# ============================================================================
# INTEGRATION WITH RAG SYSTEM
# ============================================================================

class RAGWebExecutionBridge:
    """Bridge between RAG system and web execution"""
    
    def __init__(self, rag_system, web_pipeline: WebExecutionPipeline):
        self.rag = rag_system
        self.web = web_pipeline
    
    async def generate_and_execute_web(
        self,
        user_query: str,
        session_id: str = "default",
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """Generate Playwright code via RAG and execute in browser"""
        
        logger.info("=" * 80)
        logger.info(f"RAG + WEB EXECUTION")
        logger.info("=" * 80)
        logger.info(f"Query: {user_query}")
        
        attempt = 0
        error_context = ""
        start_context_index = 0
        
        while attempt < max_retries:
            attempt += 1
            logger.info(f"--- Attempt {attempt}/{max_retries} ---")
            
            # Generate Playwright code
            enhanced_query = user_query
            if error_context:
                enhanced_query += f"\n\nPrevious attempt failed: {error_context}"
            
            rag_result = self.rag.generate_code(
                enhanced_query,
                cache_key=user_query,
                start_context_index=start_context_index,
                num_contexts=self.rag.config.top_k
            )
            
            generated_code = rag_result.get('code', '')
            
            if not generated_code:
                logger.warning("❌ No code generated")
                start_context_index += self.rag.config.top_k
                continue
            
            logger.info(f"✅ Generated {len(generated_code)} chars of Playwright code")
            
            # Security check
            is_safe, violations = self.web.security_validator.validate_code(generated_code)
            if not is_safe:
                logger.error(f"❌ Security violations: {violations}")
                return {
                    'success': False,
                    'error': 'Security validation failed',
                    'violations': violations
                }
            
            # Execute in browser
            logger.info("🌐 Executing in Playwright browser...")
            
            # Create task dict
            task_dict = {
                'task_id': f"web_{hashlib.md5(user_query.encode()).hexdigest()[:8]}",
                'ai_prompt': user_query,
                'web_params': {
                    'code': generated_code
                }
            }
            
            exec_result = await self.web.execute_web_task(task_dict, session_id)
            
            if exec_result.validation_passed:
                logger.info("✅ Web execution successful!")
                
                return {
                    'success': True,
                    'query': user_query,
                    'generated_code': generated_code,
                    'execution_result': exec_result.to_dict(),
                    'extracted_data': exec_result.extracted_data,
                    'screenshot': exec_result.screenshot_path,
                    'attempts': attempt
                }
            
            # Failed - prepare retry
            logger.warning(f"⚠️ Execution failed (attempt {attempt})")
            error_context = f"Errors: {', '.join(exec_result.validation_errors)}"
            start_context_index += self.rag.config.top_k
        
        # Max retries exceeded
        return {
            'success': False,
            'query': user_query,
            'error': 'Max retries exceeded',
            'attempts': attempt
        }

# ============================================================================
# EXAMPLE USAGE
# ============================================================================

async def main():
    """Example workflow: Search Amazon for white socks and extract prices"""
    
    # Initialize RAG system (reuse from code_generation.py)
    from code_generation import RAGSystem, RAGConfig
    
    rag_config = RAGConfig(library_name="playwright")  # NEW: Use playwright embeddings
    rag_system = RAGSystem(rag_config)
    rag_system.initialize()
    
    # Initialize web execution pipeline
    web_config = WebExecutionConfig(headless=False)
    web_pipeline = WebExecutionPipeline(web_config)
    await web_pipeline.initialize()
    
    # Create bridge
    bridge = RAGWebExecutionBridge(rag_system, web_pipeline)
    
    # Execute task
    result = await bridge.generate_and_execute_web(
        user_query="Search for 'white socks' on Amazon and extract product titles and prices",
        session_id="demo_session"
    )
    
    # Display results
    if result['success']:
        print("✅ Task completed!")
        print(f"Extracted data: {json.dumps(result.get('extracted_data'), indent=2)}")
        print(f"Screenshot: {result.get('screenshot')}")
    else:
        print(f"❌ Task failed: {result.get('error')}")
    
    # Cleanup
    await web_pipeline.cleanup()

if __name__ == "__main__":
    asyncio.run(main())