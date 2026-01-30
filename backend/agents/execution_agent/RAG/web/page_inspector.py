# ============================================================================
# PAGE INSPECTOR - DOM-AWARE CONTEXT FOR RAG (FIXED VERSION)
# ============================================================================
# ✅ Added fallback when accessibility API fails
# ✅ Better error handling for page semantics extraction

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ============================================================================
# FALLBACK PAGE SEMANTICS EXTRACTOR
# ============================================================================

async def get_page_semantics_fallback(page) -> str:
    """
    Fallback method to extract page elements when accessibility API unavailable.
    Uses direct DOM querying instead.
    
    Args:
        page: Playwright Page object
        
    Returns:
        String describing interactive elements on the page
    """
    try:
        logger.info("🔄 Using fallback method for page semantics")
        
        # Extract interactive elements using evaluate
        elements_info = await page.evaluate("""
            () => {
                const buttons = Array.from(document.querySelectorAll('button, [role="button"]'));
                const links = Array.from(document.querySelectorAll('a[href]'));
                const inputs = Array.from(document.querySelectorAll('input, textarea, select'));
                
                return {
                    buttons: buttons.slice(0, 10).map(el => ({
                        text: el.textContent?.trim() || el.ariaLabel || el.title || 'Unnamed button',
                        disabled: el.disabled || el.hasAttribute('disabled')
                    })),
                    links: links.slice(0, 15).map(el => ({
                        text: el.textContent?.trim() || el.ariaLabel || el.title || 'Unnamed link',
                        href: el.href
                    })),
                    inputs: inputs.slice(0, 10).map(el => ({
                        type: el.type || el.tagName.toLowerCase(),
                        placeholder: el.placeholder || '',
                        value: el.value || '',
                        name: el.name || el.id || 'unnamed',
                        disabled: el.disabled || el.hasAttribute('disabled')
                    }))
                };
            }
        """)
        
        descriptions = []
        
        # Format buttons
        if elements_info.get('buttons'):
            descriptions.append("BUTTONS:")
            for btn in elements_info['buttons']:
                status = " (disabled)" if btn['disabled'] else ""
                descriptions.append(f"  - '{btn['text']}'{status}")
        
        # Format inputs
        if elements_info.get('inputs'):
            descriptions.append("\nINPUT FIELDS:")
            for inp in elements_info['inputs']:
                status = " (disabled)" if inp['disabled'] else ""
                value_info = f" [current: '{inp['value']}']" if inp['value'] else ""
                placeholder_info = f" placeholder='{inp['placeholder']}'" if inp['placeholder'] else ""
                descriptions.append(f"  - {inp['type']} ({inp['name']}){placeholder_info}{value_info}{status}")
        
        # Format links
        if elements_info.get('links'):
            descriptions.append("\nLINKS:")
            for link in elements_info['links']:
                descriptions.append(f"  - '{link['text']}'")
        
        result = "\n".join(descriptions) if descriptions else "No interactive elements found on page"
        
        logger.info(f"✅ Extracted {len(elements_info.get('buttons', []))} buttons, {len(elements_info.get('inputs', []))} inputs, {len(elements_info.get('links', []))} links")
        return result
        
    except Exception as e:
        logger.error(f"❌ Fallback extraction failed: {e}")
        return "Page semantics unavailable (both methods failed)"

# ============================================================================
# PRIMARY PAGE SEMANTICS EXTRACTOR (WITH FALLBACK)
# ============================================================================

async def get_page_semantics(page) -> str:
    """
    Extract actionable elements from the current page.
    Returns natural language description for RAG context.
    
    ✅ FIXED: Now uses fallback when accessibility API fails
    
    Args:
        page: Playwright Page object
        
    Returns:
        String describing interactive elements on the page
    """
    
    try:
        # Try accessibility API first
        try:
            if not hasattr(page, 'accessibility'):
                logger.warning("⚠️ Page object missing accessibility attribute, using fallback")
                return await get_page_semantics_fallback(page)
            
            snapshot = await page.accessibility.snapshot()
            
            if not snapshot:
                logger.warning("⚠️ Accessibility snapshot returned None, using fallback")
                return await get_page_semantics_fallback(page)
            
        except (AttributeError, TypeError, Exception) as e:
            logger.warning(f"⚠️ Accessibility API failed ({type(e).__name__}: {e}), using fallback")
            return await get_page_semantics_fallback(page)
        
        # Continue with original accessibility-based extraction
        elements = []
        
        def extract_elements(node, depth=0):
            """Recursively extract interactive elements from accessibility tree"""
            if depth > 3:  # Limit depth to avoid overwhelming context
                return
            
            role = node.get('role', '')
            name = node.get('name', '')
            
            # Only include interactive elements that users can act upon
            if role in ['button', 'link', 'textbox', 'searchbox', 'combobox', 
                       'tab', 'menuitem', 'checkbox', 'radio', 'slider']:
                elements.append({
                    'role': role,
                    'label': name,
                    'enabled': not node.get('disabled', False),
                    'focused': node.get('focused', False),
                    'value': node.get('value', '')
                })
            
            # Recurse into children
            for child in node.get('children', []):
                extract_elements(child, depth + 1)
        
        extract_elements(snapshot)
        
        # Convert to natural language descriptions
        descriptions = []
        
        # Group by role for better organization
        buttons = [e for e in elements if e['role'] == 'button']
        links = [e for e in elements if e['role'] == 'link']
        inputs = [e for e in elements if e['role'] in ['textbox', 'searchbox', 'combobox']]
        
        if buttons:
            descriptions.append("BUTTONS:")
            for btn in buttons[:10]:  # Limit to top 10
                status = "" if btn['enabled'] else " (disabled)"
                descriptions.append(f"  - '{btn['label']}'{status}")
        
        if inputs:
            descriptions.append("\nINPUT FIELDS:")
            for inp in inputs[:10]:
                status = "" if inp['enabled'] else " (disabled)"
                value_info = f" [current: '{inp['value']}']" if inp['value'] else ""
                descriptions.append(f"  - {inp['role']}: '{inp['label']}'{status}{value_info}")
        
        if links:
            descriptions.append("\nLINKS:")
            for link in links[:15]:  # Limit to top 15
                descriptions.append(f"  - '{link['label']}'")
        
        result = "\n".join(descriptions) if descriptions else "No interactive elements found on page"
        
        logger.debug(f"📋 Extracted {len(elements)} page elements via accessibility API")
        return result
        
    except Exception as e:
        logger.error(f"❌ Unexpected error in get_page_semantics: {e}")
        # Last resort fallback
        return await get_page_semantics_fallback(page)


# ============================================================================
# REST OF FILE UNCHANGED - keeping original functions
# ============================================================================

async def get_page_context(page) -> Dict:
    """Get comprehensive page context including URL, title, and elements."""
    
    try:
        url = page.url
        title = await page.title()
        semantics = await get_page_semantics(page)
        
        # Get viewport info
        viewport = page.viewport_size
        
        # Check if page is loaded
        ready_state = await page.evaluate("() => document.readyState")
        
        return {
            'url': url,
            'title': title,
            'semantics': semantics,
            'viewport': viewport,
            'ready_state': ready_state,
            'is_loaded': ready_state == 'complete'
        }
    
    except Exception as e:
        logger.error(f"❌ Failed to get page context: {e}")
        return {
            'url': 'unknown',
            'title': 'unknown',
            'semantics': 'unavailable',
            'is_loaded': False,
            'error': str(e)
        }


async def wait_for_page_stable(page, timeout: int = 5000):
    """Wait for page to be stable (network idle + DOM mutations settled)."""
    
    try:
        await page.wait_for_load_state('networkidle', timeout=timeout)
        await page.wait_for_timeout(500)
        logger.debug("✅ Page is stable")
        
    except Exception as e:
        logger.debug(f"⚠️ Page may not be fully stable: {e}")


async def element_exists(page, selector: str, timeout: int = 2000) -> bool:
    """Check if an element exists on the page."""
    try:
        await page.wait_for_selector(selector, timeout=timeout, state='visible')
        return True
    except:
        return False


async def get_element_info(page, selector: str) -> Optional[Dict]:
    """Get detailed information about an element."""
    
    try:
        element = await page.query_selector(selector)
        if not element:
            return None
        
        info = await element.evaluate("""
            (el) => ({
                tagName: el.tagName,
                text: el.textContent?.trim(),
                value: el.value,
                enabled: !el.disabled,
                visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length),
                attributes: {
                    id: el.id,
                    class: el.className,
                    type: el.type,
                    placeholder: el.placeholder,
                    ariaLabel: el.getAttribute('aria-label')
                }
            })
        """)
        
        return info
        
    except Exception as e:
        logger.debug(f"Could not get element info: {e}")
        return None


async def suggest_selectors(page, description: str) -> List[str]:
    """Suggest possible selectors based on natural language description."""
    
    keywords = description.lower().split()
    selectors = []
    
    if 'search' in keywords:
        selectors.extend([
            'input[type="search"]',
            'input[placeholder*="search" i]',
            'input[aria-label*="search" i]',
            'button[aria-label*="search" i]',
            '#search',
            '.search-box'
        ])
    
    if 'button' in keywords:
        label_words = [w for w in keywords if w not in ['button', 'click', 'the', 'a']]
        if label_words:
            label = ' '.join(label_words)
            selectors.extend([
                f'button:has-text("{label}")',
                f'button[aria-label*="{label}" i]',
                f'[role="button"]:has-text("{label}")'
            ])
    
    if 'link' in keywords:
        label_words = [w for w in keywords if w not in ['link', 'click', 'the', 'a']]
        if label_words:
            label = ' '.join(label_words)
            selectors.extend([
                f'a:has-text("{label}")',
                f'[role="link"]:has-text("{label}")'
            ])
    
    return selectors


async def build_rag_context(page, task_description: str) -> str:
    """Build complete context string for RAG prompt."""
    
    context = await get_page_context(page)
    
    context_parts = [
        "="*80,
        "CURRENT PAGE STATE",
        "="*80,
        f"URL: {context['url']}",
        f"Title: {context['title']}",
        f"Page Loaded: {context['is_loaded']}",
        "",
        "AVAILABLE INTERACTIVE ELEMENTS:",
        context['semantics'],
        "",
        "="*80,
        "USER TASK",
        "="*80,
        task_description,
        "",
        "CRITICAL RULES:",
        "1. Use ONLY elements that exist in the list above",
        "2. If required element is NOT listed, print 'FAILED: Element not found'",
        "3. Do not hallucinate selectors - verify element exists first",
        "4. Print 'EXECUTION_SUCCESS' only when action truly succeeds",
        ""
    ]
    
    return "\n".join(context_parts)


async def detect_video_player(page) -> Optional[Dict]:
    """Detect video player on page and its state."""
    
    try:
        video_info = await page.evaluate("""
            () => {
                const video = document.querySelector('video');
                if (!video) return null;
                
                return {
                    exists: true,
                    paused: video.paused,
                    currentTime: video.currentTime,
                    duration: video.duration,
                    playing: !video.paused && video.currentTime > 0,
                    muted: video.muted,
                    volume: video.volume
                };
            }
        """)
        
        return video_info
        
    except Exception as e:
        logger.debug(f"No video player found: {e}")
        return None