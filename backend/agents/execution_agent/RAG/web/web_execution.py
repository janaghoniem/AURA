# ============================================================================
# WEB CODE EXECUTION - RAG + PLAYWRIGHT INTEGRATION (ENHANCED)
# ============================================================================
# ✅ ISSUE 1: Advanced bot detection bypass
# ✅ ISSUE 3: Persistent page context (NO CONFLICT with mem0 - uses separate cache)
# ✅ NEW: Page State Layer before actions
# ✅ NEW: Keyboard shortcuts for media control
# ✅ NEW: Post-action verification
# ✅ NEW: Smart intent handling when elements not listed
# ✅ NEW: State-dependent command handling

import asyncio
import logging
import json
import os
import re
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
import hashlib

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
    max_navigation_time: int = 10000
    slow_mo: int = 50  # Reduced for performance
    viewport_width: int = 1920
    viewport_height: int = 1080
    enable_verification: bool = True
    enable_page_context: bool = True
    
    # ✅ NEW: Page state layer configuration
    enable_page_state_layer: bool = True  # Observe before acting
    enable_smart_intent: bool = True      # Handle missing elements intelligently
    
    # Context caching (separate from mem0 - this is tab-level DOM cache)
    cache_page_context: bool = True
    context_cache_ttl: int = 30
    
    # Anti-detection
    use_stealth_plugin: bool = True
    randomize_fingerprint: bool = True
    use_real_user_agent: bool = True

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
    verification_message: Optional[str] = None
    page_state_before: Optional[Dict] = None  # ✅ NEW
    page_state_after: Optional[Dict] = None   # ✅ NEW

# ============================================================================
# ✅ NEW: PAGE STATE OBSERVER
# ============================================================================

class PageStateObserver:
    """
    Observes page state before actions to prevent wrong-context execution.
    Separate from mem0 - this is real-time page state, not conversation memory.
    """
    
    @staticmethod
    async def observe_page_state(page) -> Dict[str, Any]:
        """
        Observe current page state comprehensively.
        Returns dictionary with all relevant state information.
        """
        
        logger.info("👁️ Observing page state...")
        
        try:
            state = await page.evaluate("""
                () => {
                    const state = {
                        url: window.location.href,
                        title: document.title,
                        readyState: document.readyState,
                        
                        // Video state
                        video: null,
                        
                        // Page type detection
                        isYouTube: window.location.hostname.includes('youtube.com'),
                        isPlaylist: false,
                        
                        // Interactive elements
                        hasInputs: document.querySelectorAll('input, textarea').length > 0,
                        hasButtons: document.querySelectorAll('button').length > 0,
                        
                        // Focus state
                        activeElement: document.activeElement?.tagName,
                        
                        // Viewport
                        scrollPosition: window.scrollY,
                        viewportHeight: window.innerHeight,
                    };
                    
                    // Check for video element
                    const video = document.querySelector('video');
                    if (video) {
                        state.video = {
                            exists: true,
                            src: video.src || video.currentSrc,
                            paused: video.paused,
                            muted: video.muted,
                            volume: video.volume,
                            currentTime: video.currentTime,
                            duration: video.duration,
                            playing: !video.paused && video.currentTime > 0,
                            ended: video.ended,
                            readyState: video.readyState,
                            networkState: video.networkState,
                        };
                    }
                    
                    // YouTube-specific detection
                    if (state.isYouTube) {
                        // Check if playlist
                        state.isPlaylist = !!document.querySelector('[aria-label*="playlist" i], #playlist');
                        
                        // Check if player is focused
                        const player = document.querySelector('#movie_player, .html5-video-player');
                        state.playerFocused = player && player.contains(document.activeElement);
                        
                        // Check controls visibility
                        state.controlsVisible = !!document.querySelector('.ytp-chrome-bottom:not(.ytp-autohide)');
                    }
                    
                    return state;
                }
            """)
            
            logger.info(f"✅ Page state observed: video={state.get('video', {}).get('exists', False)}, "
                       f"YouTube={state.get('isYouTube', False)}, "
                       f"playlist={state.get('isPlaylist', False)}")
            
            return state
            
        except Exception as e:
            logger.error(f"❌ Failed to observe page state: {e}")
            return {
                'error': str(e),
                'url': page.url if page else 'unknown'
            }
    
    @staticmethod
    def validate_action_context(page_state: Dict, action_type: str, ai_prompt: str) -> Tuple[bool, str]:
        """
        Validate if action can be performed in current page context.
        Returns (can_proceed, reason/suggestion)
        """
        
        # Media control actions
        media_actions = ['pause', 'play', 'mute', 'unmute', 'skip', 'next', 'previous']
        
        if any(action in ai_prompt.lower() for action in media_actions):
            video_state = page_state.get('video')
            
            if not video_state or not video_state.get('exists'):
                return False, "No video element found on page. Cannot perform media control."
            
            # Check specific media action requirements
            if 'pause' in ai_prompt.lower():
                if video_state.get('paused'):
                    return False, "Video is already paused. No action needed."
            
            elif 'play' in ai_prompt.lower():
                if video_state.get('playing'):
                    return False, "Video is already playing. No action needed."
            
            elif 'mute' in ai_prompt.lower():
                if video_state.get('muted'):
                    return False, "Video is already muted. No action needed."
            
            elif 'unmute' in ai_prompt.lower():
                if not video_state.get('muted'):
                    return False, "Video is already unmuted. No action needed."
            
            elif any(word in ai_prompt.lower() for word in ['skip', 'next']):
                if not page_state.get('isPlaylist'):
                    return False, "No playlist detected. 'Skip/Next' only works in playlists. Consider seeking within video instead."
        
        return True, "Context validated - can proceed"
    
    @staticmethod
    async def compare_states(before: Dict, after: Dict) -> Dict[str, Any]:
        """
        Compare page states before and after action.
        Returns dictionary describing changes.
        """
        
        changes = {
            'url_changed': before.get('url') != after.get('url'),
            'video_state_changed': False,
            'focus_changed': before.get('activeElement') != after.get('activeElement'),
            'scroll_changed': before.get('scrollPosition') != after.get('scrollPosition'),
        }
        
        # Check video state changes
        video_before = before.get('video', {})
        video_after = after.get('video', {})
        
        if video_before.get('exists') and video_after.get('exists'):
            changes['video_state_changed'] = (
                video_before.get('paused') != video_after.get('paused') or
                video_before.get('muted') != video_after.get('muted') or
                abs(video_before.get('currentTime', 0) - video_after.get('currentTime', 0)) > 0.1
            )
            
            # Detailed video changes
            changes['video_details'] = {
                'paused_changed': video_before.get('paused') != video_after.get('paused'),
                'muted_changed': video_before.get('muted') != video_after.get('muted'),
                'time_changed': abs(video_before.get('currentTime', 0) - video_after.get('currentTime', 0)) > 0.1,
            }
        
        changes['any_change'] = any([
            changes['url_changed'],
            changes['video_state_changed'],
            changes['focus_changed'],
        ])
        
        return changes

# ============================================================================
# ✅ NEW: MEDIA KEYBOARD SHORTCUTS HANDLER
# ============================================================================

class MediaKeyboardShortcuts:
    """
    Handles media control via keyboard shortcuts (especially for YouTube).
    More reliable than clicking UI elements.
    """
    
    # YouTube keyboard shortcuts mapping
    YOUTUBE_SHORTCUTS = {
        'play': 'k',
        'pause': 'k',
        'mute': 'm',
        'unmute': 'm',
        'next': 'Shift+N',
        'previous': 'Shift+P',
        'skip': 'Shift+N',
        'fullscreen': 'f',
        'theater': 't',
        'miniplayer': 'i',
        'captions': 'c',
        'increase_speed': 'Shift+>',
        'decrease_speed': 'Shift+<',
    }
    
    @staticmethod
    async def execute_media_shortcut(page, action: str) -> Dict[str, Any]:
        """
        Execute media control using keyboard shortcut.
        Returns result with success status.
        """
        
        action_lower = action.lower()
        
        # Find matching shortcut
        shortcut = None
        for key, value in MediaKeyboardShortcuts.YOUTUBE_SHORTCUTS.items():
            if key in action_lower:
                shortcut = value
                break
        
        if not shortcut:
            return {
                'success': False,
                'error': f"No keyboard shortcut mapped for action: {action}"
            }
        
        logger.info(f"⌨️ Executing keyboard shortcut: {shortcut} for action: {action}")
        
        try:
            # Focus the video player first
            await page.evaluate("""
                () => {
                    const video = document.querySelector('video');
                    if (video) {
                        video.focus();
                    } else {
                        // Try to focus player container
                        const player = document.querySelector('#movie_player, .html5-video-player');
                        if (player) player.focus();
                    }
                }
            """)
            
            await page.wait_for_timeout(100)
            
            # Press the shortcut
            if '+' in shortcut:
                # Handle modifier keys (e.g., Shift+N)
                parts = shortcut.split('+')
                modifier = parts[0]
                key = parts[1]
                
                await page.keyboard.down(modifier)
                await page.keyboard.press(key)
                await page.keyboard.up(modifier)
            else:
                await page.keyboard.press(shortcut)
            
            await page.wait_for_timeout(300)
            
            logger.info(f"✅ Keyboard shortcut executed: {shortcut}")
            
            return {
                'success': True,
                'shortcut': shortcut,
                'action': action
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to execute keyboard shortcut: {e}")
            return {
                'success': False,
                'error': str(e)
            }

# ============================================================================
# ✅ PERSISTENT PAGE CONTEXT CACHE (SEPARATE FROM MEM0)
# ============================================================================

class PageContextCache:
    """
    Tab-level DOM context cache - completely separate from mem0.
    mem0 = conversation memory (user preferences, history)
    This = page DOM state (buttons, inputs, current elements)
    """
    
    def __init__(self, ttl_seconds: int = 30):
        self.cache: Dict[str, Dict] = {}  # session_id -> context data
        self.ttl = ttl_seconds
        self.last_analysis: Dict[str, float] = {}
    
    def should_refresh(self, session_id: str) -> bool:
        """Check if context needs refreshing"""
        if session_id not in self.last_analysis:
            return True
        
        elapsed = datetime.now().timestamp() - self.last_analysis[session_id]
        return elapsed > self.ttl
    
    async def get_or_analyze(self, session_id: str, page, force_refresh: bool = False):
        """Get cached context or analyze page if needed"""
        
        if not force_refresh and session_id in self.cache:
            if not self.should_refresh(session_id):
                logger.info(f"📦 Using cached DOM context for session {session_id}")
                return self.cache[session_id]
        
        logger.info(f"🔍 Analyzing DOM context for session {session_id}")
        
        try:
            from agents.execution_agent.RAG.web.page_inspector import get_page_context
            
            context = await get_page_context(page)
            
            self.cache[session_id] = context
            self.last_analysis[session_id] = datetime.now().timestamp()
            
            logger.info(f"✅ DOM context cached for session {session_id}")
            return context
            
        except Exception as e:
            logger.error(f"❌ Failed to analyze DOM context: {e}")
            return {
                'url': page.url if page else 'unknown',
                'title': 'unknown',
                'semantics': 'unavailable',
                'error': str(e)
            }
    
    def invalidate(self, session_id: str):
        """Invalidate cache (e.g., after navigation)"""
        if session_id in self.cache:
            del self.cache[session_id]
            logger.info(f"🗑️ Invalidated DOM cache for session {session_id}")

# ============================================================================
# ✅ ADVANCED STEALTH BROWSER
# ============================================================================

class StealthBrowser:
    """Advanced browser fingerprint randomization and bot detection bypass"""
    
    @staticmethod
    def get_random_user_agent() -> str:
        """Generate realistic user agent"""
        import random
        
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        ]
        return random.choice(user_agents)
    
    @staticmethod
    def get_random_viewport() -> Dict[str, int]:
        """Generate realistic viewport size"""
        import random
        
        common_resolutions = [
            {'width': 1920, 'height': 1080},
            {'width': 1366, 'height': 768},
            {'width': 1536, 'height': 864},
            {'width': 1440, 'height': 900},
        ]
        return random.choice(common_resolutions)
    
    @staticmethod
    async def inject_stealth_scripts(context):
        """Inject comprehensive anti-detection scripts"""
        
        stealth_script = """
        // Override navigator.webdriver
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
            configurable: true
        });
        
        // Mock Chrome runtime
        window.chrome = {
            runtime: {
                connect: () => {},
                sendMessage: () => {},
            },
            loadTimes: function() {
                return {
                    commitLoadTime: Date.now() / 1000 - Math.random() * 10,
                    connectionInfo: 'http/1.1',
                    finishDocumentLoadTime: Date.now() / 1000 - Math.random() * 5,
                    firstPaintTime: Date.now() / 1000 - Math.random() * 7,
                };
            }
        };
        
        // Override permissions API
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
        
        // Mock plugins
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });
        
        // Override languages
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en']
        });
        
        // Hide automation properties
        delete window.__playwright;
        delete window.__pw_manual;
        
        console.log('✅ Stealth mode activated');
        """
        
        await context.add_init_script(stealth_script)
        logger.info("✅ Advanced stealth scripts injected")
    
    @staticmethod
    def get_stealth_launch_args() -> List[str]:
        """Get comprehensive launch arguments for stealth mode"""
        return [
            '--disable-blink-features=AutomationControlled',
            '--disable-dev-shm-usage',
            '--disable-web-security',
            '--disable-features=IsolateOrigins,site-per-process',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-infobars',
            '--window-size=1920,1080',
            '--start-maximized',
            '--disable-notifications',
            '--disable-popup-blocking',
            '--disable-background-timer-throttling',
            '--disable-backgrounding-occluded-windows',
            '--disable-renderer-backgrounding',
        ]

# ============================================================================
# ENHANCED WEB EXECUTION PIPELINE
# ============================================================================

class WebExecutionPipeline:
    """
    Enhanced pipeline with:
    - Page state layer (observe before acting)
    - Keyboard shortcuts for media
    - Post-action verification
    - Smart intent handling
    - Persistent context (separate from mem0)
    """
    
    def __init__(self, config: WebExecutionConfig):
        self.config = config
        self.playwright = None
        self.browser = None
        self.context = None
        self.sessions = {}
        self._rag_system = None
        self.shared_groq_client = None
        
        # ✅ NEW: Helper classes
        self.context_cache = PageContextCache(ttl_seconds=config.context_cache_ttl)
        self.stealth = StealthBrowser()
        self.state_observer = PageStateObserver()
        self.media_shortcuts = MediaKeyboardShortcuts()
        
        Path(self.config.screenshot_dir).mkdir(parents=True, exist_ok=True)
    
    async def initialize(self):
        """Initialize Playwright with advanced stealth mode"""
        try:
            from playwright.async_api import async_playwright
            
            logger.info("🚀 Initializing Playwright with advanced stealth...")
            
            self.playwright = await async_playwright().start()
            
            launch_args = self.stealth.get_stealth_launch_args()
            
            self.browser = await self.playwright.chromium.launch(
                headless=self.config.headless,
                slow_mo=self.config.slow_mo,
                args=launch_args
            )
            
            viewport = self.stealth.get_random_viewport() if self.config.randomize_fingerprint else {
                'width': self.config.viewport_width,
                'height': self.config.viewport_height
            }
            
            user_agent = self.stealth.get_random_user_agent() if self.config.use_real_user_agent else None
            
            context_options = {
                'viewport': viewport,
                'locale': 'en-US',
                'timezone_id': 'America/New_York',
                'permissions': ['geolocation', 'notifications'],
                'geolocation': {'longitude': -74.006, 'latitude': 40.7128},
                'extra_http_headers': {
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                }
            }
            
            if user_agent:
                context_options['user_agent'] = user_agent
            
            self.context = await self.browser.new_context(**context_options)
            
            if self.config.use_stealth_plugin:
                await self.stealth.inject_stealth_scripts(self.context)
            
            logger.info("✅ Advanced stealth Playwright initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Playwright: {e}")
            raise
    
    async def get_or_create_page(self, session_id: str):
        """Get existing page for session or create new one"""
        if session_id not in self.sessions or self.sessions[session_id].is_closed():
            page = await self.context.new_page()
            self.sessions[session_id] = page
            logger.info(f"📄 Created new page for session {session_id}")
        
        return self.sessions[session_id]
    
    async def _initialize_rag_system(self):
        """Lazy initialize RAG system"""
        if self._rag_system is not None:
            return
        
        try:
            logger.info("🧠 Initializing Playwright RAG system...")
            
            from agents.execution_agent.RAG.web.code_generation import (
                PlaywrightRAGSystem,
                PlaywrightRAGConfig
            )
            
            rag_config = PlaywrightRAGConfig()
            
            self._rag_system = PlaywrightRAGSystem(
                rag_config,
                llm_client=self.shared_groq_client
            )
            self._rag_system.initialize()
            
            logger.info("✅ Playwright RAG system initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize RAG: {e}")
            raise
    
    async def execute_web_task(
        self,
        task: Dict[str, Any],
        session_id: str = "default"
    ) -> WebExecutionResult:
        """
        Execute web task with FULL enhancements:
        1. Page state observation
        2. Context validation
        3. Smart intent handling
        4. Keyboard shortcuts for media
        5. Post-action verification
        """
        
        start_time = datetime.now()
        task_id = task.get('task_id', 'unknown')
        
        logger.info(f"⚡ Executing web task {task_id}")
        
        try:
            page = await self.get_or_create_page(session_id)
            ai_prompt = task.get('ai_prompt', '')
            
            # Validation
            if not ai_prompt:
                return WebExecutionResult(
                    validation_passed=False,
                    security_passed=True,
                    validation_errors=["No ai_prompt provided"],
                    execution_time=(datetime.now() - start_time).total_seconds()
                )
            
            # ✅ STEP 1: OBSERVE PAGE STATE BEFORE ACTION
            page_state_before = None
            if self.config.enable_page_state_layer:
                page_state_before = await self.state_observer.observe_page_state(page)
                
                # Validate action context
                action_type = task.get('web_params', {}).get('action', 'unknown')
                can_proceed, reason = self.state_observer.validate_action_context(
                    page_state_before, action_type, ai_prompt
                )
                
                if not can_proceed:
                    logger.warning(f"⚠️ Context validation failed: {reason}")
                    return WebExecutionResult(
                        validation_passed=False,
                        security_passed=True,
                        error=f"Context validation failed: {reason}",
                        page_state_before=page_state_before,
                        execution_time=(datetime.now() - start_time).total_seconds()
                    )
            
            action_type = task.get('web_params', {}).get('action', 'unknown')
            
            # Check if navigation (invalidate cache)
            if action_type == 'navigate':
                self.context_cache.invalidate(session_id)
            
            # ✅ STEP 2: CHECK FOR MEDIA CONTROL VIA KEYBOARD SHORTCUTS
            media_keywords = ['pause', 'play', 'mute', 'unmute', 'skip', 'next', 'previous']
            is_media_action = any(keyword in ai_prompt.lower() for keyword in media_keywords)
            
            if is_media_action and page_state_before and page_state_before.get('isYouTube'):
                logger.info("🎬 Detected media control on YouTube - using keyboard shortcuts")
                
                shortcut_result = await self.media_shortcuts.execute_media_shortcut(page, ai_prompt)
                
                if shortcut_result['success']:
                    # Wait for state change
                    await page.wait_for_timeout(500)
                    
                    # Observe state after
                    page_state_after = await self.state_observer.observe_page_state(page)
                    
                    # Verify the change
                    changes = await self.state_observer.compare_states(page_state_before, page_state_after)
                    
                    if changes['video_state_changed']:
                        logger.info(f"✅ Media control succeeded via keyboard shortcut")
                        
                        return WebExecutionResult(
                            validation_passed=True,
                            security_passed=True,
                            output=f"EXECUTION_SUCCESS: Media control via keyboard shortcut ({shortcut_result['shortcut']})",
                            page_url=page.url,
                            page_title=await page.title(),
                            page_state_before=page_state_before,
                            page_state_after=page_state_after,
                            verification_message=f"Video state changed: {changes['video_details']}",
                            execution_time=(datetime.now() - start_time).total_seconds()
                        )
                    else:
                        logger.warning(f"⚠️ Keyboard shortcut executed but no state change detected")
                else:
                    logger.info(f"ℹ️ Keyboard shortcut failed, falling back to RAG generation")
            
            # ✅ STEP 3: GENERATE CODE WITH ENHANCED PROMPT (SMART INTENT)
            logger.info(f"🧠 Using RAG to generate code from: {ai_prompt}")
            
            try:
                generated_code = await self._generate_code_from_rag_smart(
                    ai_prompt, page, task, session_id, page_state_before
                )
                
            except Exception as e:
                logger.error(f"❌ RAG generation failed: {e}")
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
            
            # ✅ STEP 4: EXECUTE CODE
            logger.info(f"🚀 Executing RAG-generated code")
            result = await self._execute_generated_code(page, generated_code, task_id)
            
            # ✅ STEP 5: OBSERVE STATE AFTER ACTION
            page_state_after = None
            if self.config.enable_page_state_layer:
                page_state_after = await self.state_observer.observe_page_state(page)
            
            # ✅ STEP 6: POST-ACTION VERIFICATION
            verification_passed = True
            verification_message = None
            
            if self.config.enable_verification and result.get('success'):
                # Compare states
                if page_state_before and page_state_after:
                    changes = await self.state_observer.compare_states(page_state_before, page_state_after)
                    
                    if changes['any_change']:
                        verification_message = f"✅ Page state changed as expected: {changes}"
                        logger.info(f"✅ Verification: State changed")
                    else:
                        verification_message = "⚠️ No page state change detected"
                        logger.warning(f"⚠️ Verification: No state change")
                
                # Additional verification from verifiers module
                from agents.execution_agent.RAG.web.verifiers import verify_action
                
                verify_context = {
                    'url_before': page_state_before.get('url') if page_state_before else page.url,
                    'text': task.get('web_params', {}).get('text'),
                    'task_id': task_id,
                    'extracted_data': result.get('extracted_data')
                }
                
                verification_passed, verify_msg = await verify_action(
                    page, 
                    action_type, 
                    verify_context
                )
                
                if verification_message:
                    verification_message += f" | {verify_msg}"
                else:
                    verification_message = verify_msg
                
                if not verification_passed:
                    logger.error(f"❌ Verification failed: {verification_message}")
                    result['success'] = False
                    result['error'] = f"Action executed but verification failed: {verification_message}"
            
            # Get final page info
            page_url = page.url
            page_title = await page.title()
            
            # Update context cache in background
            if result.get('success') and self.config.cache_page_context:
                asyncio.create_task(
                    self.context_cache.get_or_analyze(session_id, page, force_refresh=True)
                )
            
            # Screenshot
            screenshot_path = None
            if self.config.screenshots_enabled:
                screenshot_path = os.path.join(
                    self.config.screenshot_dir,
                    f"{task_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                )
                await page.screenshot(path=screenshot_path)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"✅ Task {task_id} completed in {execution_time:.2f}s")
            
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
                verification_message=verification_message,
                page_state_before=page_state_before,
                page_state_after=page_state_after
            )
            
        except asyncio.TimeoutError:
            logger.error(f"⏰ Task {task_id} timed out")
            return WebExecutionResult(
                validation_passed=False,
                security_passed=True,
                error=f"Timeout after {self.config.timeout_seconds}s",
                execution_time=(datetime.now() - start_time).total_seconds()
            )
        
        except Exception as e:
            logger.error(f"❌ Task {task_id} failed: {e}")
            import traceback
            return WebExecutionResult(
                validation_passed=False,
                security_passed=True,
                error=f"{str(e)}\n{traceback.format_exc()}",
                execution_time=(datetime.now() - start_time).total_seconds()
            )
    
    async def _generate_code_from_rag_smart(
        self, 
        ai_prompt: str, 
        page, 
        task: Dict[str, Any],
        session_id: str,
        page_state: Optional[Dict] = None
    ) -> str:
        """
        Generate code with SMART INTENT HANDLING.
        ✅ Enhanced prompt that handles missing elements intelligently.
        """
        
        await self._initialize_rag_system()
        
        # Get cached DOM context
        page_context = await self.context_cache.get_or_analyze(session_id, page)
        
        # ✅ NEW: Build enhanced prompt with smart intent handling
        if self.config.enable_page_context:
            enhanced_prompt = f"""
# CURRENT PAGE STATE
URL: {page_context.get('url', 'unknown')}
Title: {page_context.get('title', 'unknown')}

# PAGE STATE INFORMATION
{json.dumps(page_state, indent=2) if page_state else 'State not available'}

# AVAILABLE INTERACTIVE ELEMENTS
{page_context.get('semantics', 'unavailable')}

# USER TASK
{ai_prompt}

================================================================
ENHANCED RULES WITH SMART INTENT HANDLING:
================================================================

1. **Primary Approach**: Use ONLY elements that exist in the list above

2. **Smart Intent for Missing Elements**: 
   If the required element is NOT listed (e.g., mute button, volume control):
   
   a) For YouTube/Video sites:
      - Use keyboard shortcuts instead of clicking UI elements
      - Example: For "mute" → press 'm' key
      - Example: For "pause" → press 'k' key
      - Example: For "next video" → press 'Shift+N'
   
   b) For other missing elements:
      - Try alternative selectors (aria-label, data attributes)
      - Use page.evaluate() to directly manipulate DOM
      - Example: `await page.evaluate('() => document.querySelector("video").muted = true')`
   
   c) Last resort:
      - Print clear explanation of what was attempted
      - Suggest user to provide more context

3. **Success Criteria**:
   - Print 'EXECUTION_SUCCESS' ONLY when the intended outcome is achieved
   - Verify state change when possible
   - For media controls: check video element state after action

4. **Failure Handling**:
   - If element truly doesn't exist and no alternative works:
     Print 'FAILED: [specific reason]' with what you tried

================================================================
KEYBOARD SHORTCUTS (USE THESE WHEN UI ELEMENTS MISSING):
================================================================

YouTube Media Control:
- Play/Pause: 'k'
- Mute/Unmute: 'm'
- Next video: 'Shift+N'
- Previous video: 'Shift+P'
- Fullscreen: 'f'
- Increase speed: 'Shift+>'
- Decrease speed: 'Shift+<'

General:
- Tab: Navigate between elements
- Enter: Activate focused element
- Escape: Close dialogs/fullscreen

================================================================

Generate code that intelligently handles the task even if exact UI elements are not listed.
"""
        else:
            enhanced_prompt = ai_prompt
        
        logger.info(f"🧠 RAG Query with smart intent handling")
        
        try:
            rag_result = self._rag_system.generate_code(
                enhanced_prompt,
                include_explanation=False
            )
            
            generated_code = rag_result.get('code', '')
            
            if not generated_code:
                raise ValueError("RAG system returned empty code")
            
            logger.info(f"✅ RAG generated {len(generated_code)} chars of code")
            
            return generated_code
            
        except Exception as e:
            logger.error(f"❌ RAG code generation failed: {e}")
            raise
    
    async def _execute_generated_code(
        self,
        page,
        code: str,
        task_id: str
    ) -> Dict[str, Any]:
        """Execute RAG-generated Playwright code with enhanced error detection"""
        
        logger.info(f"🚀 Executing generated code for task {task_id}")
        
        try:
            # Clean code
            code = re.sub(r'\nasyncio\.run\(main\(\)\)\s*$', '', code, flags=re.MULTILINE)
            code = re.sub(
                r'if\s+__name__\s*==\s*["\']__main__["\']\s*:\s*\n?\s*asyncio\.run\(main\(\)\)',
                '',
                code,
                flags=re.MULTILINE | re.DOTALL
            )
            code = re.sub(r'asyncio\.run\([^)]+\)', '', code)
            code = re.sub(r'await\s+browser\.close\(\)', 'pass  # Browser kept open', code)
            code = re.sub(r'browser\.close\(\)', 'pass  # Browser kept open', code)
            code = re.sub(r'await\s+context\.close\(\)', 'pass  # Context kept open', code)
            code = re.sub(r'context\.close\(\)', 'pass  # Context kept open', code)
            code = re.sub(r'await\s+playwright\.stop\(\)', 'pass  # Playwright kept running', code)
            
            # Wrap in async function
            def _indent(text, spaces=4):
                return '\n'.join((' ' * spaces) + line if line.strip() else line for line in text.splitlines())
            
            wrapped_code = f"""
import sys
from io import StringIO

_stdout_capture = StringIO()
_original_stdout = sys.stdout

async def __rag_step__(page):
    sys.stdout = _stdout_capture
    
    try:
{_indent(code, 8)}
    finally:
        sys.stdout = _original_stdout
"""
            
            exec_namespace = {
                'page': page,
                'asyncio': asyncio,
                '__result__': None,
                '__stdout__': ''
            }
            
            exec(wrapped_code, exec_namespace)
            
            logger.info(f"⚡ Executing wrapped code...")
            result_data = await exec_namespace['__rag_step__'](page)
            
            stdout_content = exec_namespace['_stdout_capture'].getvalue()
            exec_namespace['__stdout__'] = stdout_content
            
            if exec_namespace.get('__result__') is not None:
                result_data = exec_namespace['__result__']
            
            # Parse stdout for success/failure
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
            logger.error(f"❌ Code execution failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _parse_execution_output(self, stdout: str) -> Tuple[bool, str]:
        """Parse stdout to determine success/failure"""
        
        if 'FAILED:' in stdout:
            failure_msg = stdout.split('FAILED:')[1].split('\n')[0].strip()
            return False, f"Playwright error: {failure_msg}"
        
        if 'Timeout' in stdout and 'exceeded' in stdout:
            return False, "Playwright timeout exceeded"
        
        if 'not found' in stdout.lower() or 'cannot find' in stdout.lower():
            return False, "Required element not found on page"
        
        if 'EXECUTION_SUCCESS' in stdout:
            return True, "Execution successful"
        
        if len(stdout.strip()) > 0:
            return True, "Code executed (no explicit success marker)"
        
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
        
        return {
            'passed': len(violations) == 0,
            'violations': violations
        }
    
    async def cleanup(self):
        """Clean up browser resources"""
        logger.info("🧹 Cleaning up Playwright resources...")
        
        try:
            active_sessions = list(self.sessions.keys())
            self.context_cache.cleanup_closed_sessions(active_sessions)
            
            for session_id, page in self.sessions.items():
                if not page.is_closed():
                    await page.close()
            
            if self.context:
                await self.context.close()
            
            if self.browser:
                await self.browser.close()
            
            if self.playwright:
                await self.playwright.stop()
            
            logger.info("✅ Playwright cleanup complete")
            
        except Exception as e:
            logger.error(f"❌ Error during cleanup: {e}")

# ============================================================================
# TASK MODELS (keep existing from original file)
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
        """Execute a single web ActionTask using enhanced pipeline"""
        
        logger.info(f"🌐 Processing web task {task.task_id}: {task.ai_prompt[:50]}...")
        
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
            logger.info(f"🔄 Attempt {attempt}/{max_retries} for task {task.task_id}")
            
            try:
                task_dict = {
                    'task_id': task.task_id,
                    'ai_prompt': task.ai_prompt,
                    'web_params': task.web_params
                }
                
                exec_result = await self.web.execute_web_task(task_dict, session_id)
                
                if exec_result.validation_passed and exec_result.security_passed:
                    logger.info(f"✅ Task {task.task_id} completed successfully")
                    return self.adapter.execution_result_to_task_result(task, exec_result)
                
                logger.warning(f"⚠️ Execution failed (attempt {attempt})")
                
            except Exception as e:
                logger.error(f"❌ Exception during web execution: {e}")
                if attempt == max_retries:
                    break
        
        logger.error(f"❌ Task {task.task_id} failed after {max_retries} attempts")
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
            
            logger.info(f"📨 Web execution agent received task {task.task_id}")
            
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
            logger.info(f"✅ Sent result for task {task.task_id}: {result.status}")
            
        except Exception as e:
            logger.error(f"❌ Error processing web execution request: {e}")
            
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
    
    logger.info("✅ Web Execution Agent started with FULL enhancements")
    logger.info("   ✅ Page state layer")
    logger.info("   ✅ Keyboard shortcuts for media")
    logger.info("   ✅ Post-action verification")
    logger.info("   ✅ Smart intent handling")
    logger.info("   ✅ Persistent context (separate from mem0)")
    
    while True:
        await asyncio.sleep(1)

async def initialize_web_execution_agent_for_server(broker_instance):
    """Server-compatible initialization for web execution agent with all enhancements"""
    
    from dotenv import load_dotenv
    load_dotenv()
    
    if hasattr(broker_instance, '_web_rag_execution_subscribed'):
        logger.warning("⚠️ Web RAG Execution agent already subscribed, skipping")
        return
    broker_instance._web_rag_execution_subscribed = True
    
    try:
        from agents.execution_agent.RAG.web.code_generation import RAGSystem, RAGConfig
        
        try:
            logger.info("🧠 Initializing RAG system for Playwright...")
            rag_config = RAGConfig(library_name="playwright")
            rag_system = RAGSystem(rag_config)
            rag_system.initialize()
            logger.info("✅ Playwright RAG system ready")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Playwright RAG: {e}")
            raise
        
        try:
            logger.info("🚀 Initializing enhanced Playwright web pipeline...")
            
            web_config = WebExecutionConfig(
                headless=False,
                timeout_seconds=30,
                enable_verification=True,
                enable_page_context=True,
                enable_page_state_layer=True,  # ✅ NEW
                enable_smart_intent=True,      # ✅ NEW
                cache_page_context=True,
                use_stealth_plugin=True,
                randomize_fingerprint=True,
                use_real_user_agent=True,
            )
            web_pipeline = WebExecutionPipeline(web_config)
            await web_pipeline.initialize()
            
            logger.info("✅ Enhanced Playwright web pipeline ready")
            
        except Exception as e:
            logger.error(f"❌ Web pipeline initialization error: {e}")
            raise
        
        logger.info("🌐 Starting enhanced web execution agent...")
        await start_web_execution_agent_with_rag(broker_instance, rag_system, web_pipeline)
    
    except Exception as e:
        logger.error(f"❌ Failed to initialize web execution agent: {e}")
        raise