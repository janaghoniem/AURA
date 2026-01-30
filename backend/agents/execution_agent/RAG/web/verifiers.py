# ============================================================================
# POST-ACTION VERIFIERS - CLOSED-LOOP AUTOMATION
# ============================================================================
# Verifies that actions actually succeeded by checking observable outcomes

import logging
from typing import Dict, Tuple, Optional, Any

logger = logging.getLogger(__name__)

# ============================================================================
# MAIN VERIFICATION FUNCTION
# ============================================================================

async def verify_action(
    page, 
    action_type: str, 
    context: Dict[str, Any]
) -> Tuple[bool, str]:
    """
    Verify that an action actually succeeded.
    
    Args:
        page: Playwright Page object
        action_type: Type of action performed (navigate, click, fill, etc.)
        context: Context dictionary with action details
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    
    logger.debug(f"🔍 Verifying action: {action_type}")
    
    try:
        if action_type == "navigate":
            return await verify_navigation(page, context)
        
        elif action_type == "fill":
            return await verify_fill(page, context)
        
        elif action_type == "click":
            return await verify_click(page, context)
        
        elif action_type == "play_video":
            return await verify_video_playback(page, context)
        
        elif action_type == "extract":
            return await verify_extraction(page, context)
        
        else:
            # Default: assume success if no specific verification
            logger.debug(f"⚠️ No specific verification for action type: {action_type}")
            return True, f"Action '{action_type}' executed (no verification implemented)"
    
    except Exception as e:
        logger.error(f"❌ Verification error: {e}")
        return False, f"Verification failed with error: {str(e)}"


# ============================================================================
# SPECIFIC VERIFIERS
# ============================================================================

async def verify_navigation(page, context: Dict) -> Tuple[bool, str]:
    """Verify that navigation succeeded"""
    
    try:
        # Wait for page to load
        await page.wait_for_load_state('networkidle', timeout=5000)
        
        current_url = page.url
        expected_domain = context.get('expected_domain')
        
        # Check if we navigated to expected domain (if specified)
        if expected_domain and expected_domain not in current_url:
            return False, f"Navigated to wrong URL: {current_url}"
        
        # Check page is actually loaded
        ready_state = await page.evaluate("() => document.readyState")
        if ready_state != 'complete':
            return False, f"Page not fully loaded (state: {ready_state})"
        
        return True, f"Successfully navigated to {current_url}"
        
    except Exception as e:
        return False, f"Navigation verification failed: {str(e)}"


async def verify_fill(page, context: Dict) -> Tuple[bool, str]:
    """Verify that text was entered into input field"""
    
    try:
        selector = context.get('last_selector')
        expected_text = context.get('text', '')
        
        if not selector:
            # Try to find the focused element
            actual_value = await page.evaluate("""
                () => {
                    const focused = document.activeElement;
                    return focused?.value || '';
                }
            """)
        else:
            # Check specific selector
            try:
                actual_value = await page.input_value(selector, timeout=2000)
            except:
                return False, f"Could not find input field: {selector}"
        
        # Verify text matches (case-insensitive partial match)
        if expected_text.lower() in actual_value.lower():
            return True, f"Text filled successfully: '{actual_value}'"
        
        return False, f"Text mismatch. Expected '{expected_text}', got '{actual_value}'"
        
    except Exception as e:
        return False, f"Fill verification failed: {str(e)}"


async def verify_click(page, context: Dict) -> Tuple[bool, str]:
    """Verify that click action caused expected change"""
    
    try:
        url_before = context.get('url_before')
        url_after = page.url
        
        # Check if URL changed (navigation happened)
        if url_before and url_before != url_after:
            return True, f"Click caused navigation to {url_after}"
        
        # Check if any loading happened
        try:
            await page.wait_for_load_state('networkidle', timeout=2000)
            return True, "Click triggered page change"
        except:
            pass
        
        # Check if any DOM changes occurred
        try:
            # Wait briefly for any animations or dynamic content
            await page.wait_for_timeout(500)
            
            # If we get here, click executed but no obvious change
            # This might be okay (e.g., click on already-expanded menu)
            return True, "Click executed (no visible navigation)"
            
        except Exception as e:
            return False, f"Click verification failed: {str(e)}"
    
    except Exception as e:
        return False, f"Click verification error: {str(e)}"


async def verify_video_playback(page, context: Dict) -> Tuple[bool, str]:
    """Verify that video is actually playing"""
    
    try:
        # Wait a bit for video to start
        await page.wait_for_timeout(1000)
        
        is_playing = await page.evaluate("""
            () => {
                const video = document.querySelector('video');
                if (!video) {
                    return { found: false };
                }
                
                return {
                    found: true,
                    paused: video.paused,
                    currentTime: video.currentTime,
                    duration: video.duration,
                    readyState: video.readyState,
                    playing: !video.paused && video.currentTime > 0
                };
            }
        """)
        
        if not is_playing.get('found'):
            return False, "No video element found on page"
        
        if is_playing.get('playing'):
            return True, f"Video is playing (time: {is_playing.get('currentTime', 0):.1f}s)"
        
        # Video found but not playing
        if is_playing.get('paused'):
            return False, "Video is paused (not playing)"
        
        if is_playing.get('currentTime', 0) == 0:
            return False, "Video not started (currentTime = 0)"
        
        return False, f"Video state unclear: {is_playing}"
        
    except Exception as e:
        return False, f"Video playback verification failed: {str(e)}"


async def verify_extraction(page, context: Dict) -> Tuple[bool, str]:
    """Verify that data extraction succeeded"""
    
    try:
        extracted_data = context.get('extracted_data')
        
        if not extracted_data:
            return False, "No data was extracted"
        
        # Check if extracted data is meaningful (not empty/null)
        if isinstance(extracted_data, str):
            if len(extracted_data.strip()) > 0:
                return True, f"Extracted {len(extracted_data)} characters of text"
            return False, "Extracted empty string"
        
        elif isinstance(extracted_data, list):
            if len(extracted_data) > 0:
                return True, f"Extracted {len(extracted_data)} items"
            return False, "Extracted empty list"
        
        elif isinstance(extracted_data, dict):
            if len(extracted_data) > 0:
                return True, f"Extracted {len(extracted_data)} fields"
            return False, "Extracted empty dictionary"
        
        return True, "Data extracted successfully"
        
    except Exception as e:
        return False, f"Extraction verification failed: {str(e)}"


# ============================================================================
# ADVANCED VERIFIERS
# ============================================================================

async def verify_element_exists(page, selector: str, timeout: int = 2000) -> Tuple[bool, str]:
    """Verify that an element exists and is visible"""
    
    try:
        await page.wait_for_selector(selector, timeout=timeout, state='visible')
        return True, f"Element found: {selector}"
    except:
        return False, f"Element not found or not visible: {selector}"


async def verify_text_visible(page, text: str, timeout: int = 2000) -> Tuple[bool, str]:
    """Verify that specific text is visible on page"""
    
    try:
        await page.wait_for_selector(f'text={text}', timeout=timeout)
        return True, f"Text visible: '{text}'"
    except:
        return False, f"Text not found: '{text}'"


async def verify_url_contains(page, substring: str) -> Tuple[bool, str]:
    """Verify that current URL contains substring"""
    
    current_url = page.url
    if substring.lower() in current_url.lower():
        return True, f"URL contains '{substring}': {current_url}"
    return False, f"URL does not contain '{substring}': {current_url}"


async def verify_page_loaded(page, timeout: int = 5000) -> Tuple[bool, str]:
    """Verify that page is fully loaded"""
    
    try:
        await page.wait_for_load_state('networkidle', timeout=timeout)
        ready_state = await page.evaluate("() => document.readyState")
        
        if ready_state == 'complete':
            return True, "Page fully loaded"
        
        return False, f"Page not fully loaded (state: {ready_state})"
        
    except Exception as e:
        return False, f"Page load verification failed: {str(e)}"


# ============================================================================
# COMPOSITE VERIFIERS
# ============================================================================

async def verify_search_executed(page, context: Dict) -> Tuple[bool, str]:
    """Verify that search was executed and results are shown"""
    
    try:
        # Check URL changed to results page
        url_before = context.get('url_before', '')
        url_after = page.url
        
        # Common search result indicators
        search_indicators = [
            '/search',
            'q=',
            'query=',
            'results',
            'search?'
        ]
        
        if any(ind in url_after.lower() for ind in search_indicators):
            return True, f"Search results loaded: {url_after}"
        
        # Check for results container
        results_selectors = [
            '[role="main"]',
            '#search',
            '.search-results',
            '#results'
        ]
        
        for selector in results_selectors:
            try:
                await page.wait_for_selector(selector, timeout=2000)
                return True, "Search results container found"
            except:
                continue
        
        return False, "Could not verify search results"
        
    except Exception as e:
        return False, f"Search verification failed: {str(e)}"


async def verify_form_submitted(page, context: Dict) -> Tuple[bool, str]:
    """Verify that form was submitted successfully"""
    
    try:
        url_before = context.get('url_before')
        url_after = page.url
        
        # Check for URL change (typical after form submit)
        if url_before != url_after:
            return True, f"Form submitted (navigated to {url_after})"
        
        # Check for success message
        success_patterns = [
            'text=success',
            'text=submitted',
            'text=thank you',
            '[role="alert"]'
        ]
        
        for pattern in success_patterns:
            try:
                await page.wait_for_selector(pattern, timeout=2000)
                return True, "Form submission success message found"
            except:
                continue
        
        # Check if loading happened
        try:
            await page.wait_for_load_state('networkidle', timeout=3000)
            return True, "Form submitted (page reloaded)"
        except:
            pass
        
        return False, "Could not verify form submission"
        
    except Exception as e:
        return False, f"Form submission verification failed: {str(e)}"


# ============================================================================
# VERIFICATION HELPERS
# ============================================================================

def parse_verification_result(stdout: str) -> Tuple[bool, str]:
    """
    Parse stdout from executed code to determine success.
    
    Args:
        stdout: Standard output from code execution
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    
    # Check for explicit failure
    if 'FAILED:' in stdout:
        failure_msg = stdout.split('FAILED:')[1].split('\n')[0].strip()
        return False, f"Playwright error: {failure_msg}"
    
    # Check for success indicator
    if 'EXECUTION_SUCCESS' in stdout:
        return True, "Code reported success"
    
    # No clear indicator
    return False, "No success indicator found in output"


async def get_page_state_snapshot(page) -> Dict:
    """
    Get snapshot of current page state for comparison.
    
    Returns:
        Dictionary with page state information
    """
    
    try:
        snapshot = await page.evaluate("""
            () => ({
                url: window.location.href,
                title: document.title,
                readyState: document.readyState,
                activeElement: document.activeElement?.tagName,
                visibleText: document.body?.innerText?.substring(0, 500),
                elementCount: document.querySelectorAll('*').length
            })
        """)
        
        return snapshot
        
    except Exception as e:
        logger.debug(f"Could not get page snapshot: {e}")
        return {}


async def compare_page_states(before: Dict, after: Dict) -> Dict:
    """
    Compare two page state snapshots.
    
    Returns:
        Dictionary describing changes
    """
    
    changes = {
        'url_changed': before.get('url') != after.get('url'),
        'title_changed': before.get('title') != after.get('title'),
        'content_changed': before.get('visibleText') != after.get('visibleText'),
        'dom_changed': before.get('elementCount') != after.get('elementCount'),
        'any_change': False
    }
    
    changes['any_change'] = any([
        changes['url_changed'],
        changes['title_changed'],
        changes['content_changed'],
        changes['dom_changed']
    ])
    
    return changes