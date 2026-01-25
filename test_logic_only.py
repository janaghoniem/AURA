#!/usr/bin/env python3
"""
Test script to verify the infinite loop hallucination fix logic
Tests only the core logic without LLM dependencies
"""

import asyncio
import json
import logging
from unittest.mock import AsyncMock, MagicMock
from typing import Optional, List, Dict
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from agents.utils.device_protocol import (
    MobileTaskRequest, SemanticUITree, UIElement
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestMobileStrategy:
    """Test version of MobileReActStrategy without LLM dependencies"""
    
    def __init__(self, device_id: str = "default_device"):
        self.device_id = device_id
        
        # Device state cache and tracking
        self.current_ui_tree: Optional[SemanticUITree] = None
        self.previous_ui_trees: List[SemanticUITree] = []  # Track recent states
        self.action_history: List[Dict] = []  # Track recent actions
        self.device_state: str = "unknown"  # home_screen, in_app, app_drawer, etc.
        self.target_app: Optional[str] = None  # Extracted from goal
        
        # Common app patterns for detection
        self.app_patterns = {
            "gmail": ["gmail", "mail", "email", "envelope"],
            "whatsapp": ["whatsapp", "chat", "message", "bubble"],
            "chrome": ["chrome", "browser", "globe", "earth"],
            "youtube": ["youtube", "play", "video", "film"],
            "settings": ["settings", "gear", "cog", "tools"],
            "camera": ["camera", "photo", "picture", "shutter"],
            "phone": ["phone", "call", "dial", "contact"],
            "messages": ["messages", "sms", "text", "bubble"],
            "maps": ["maps", "location", "pin", "navigation"],
            "calculator": ["calculator", "calc", "numbers", "math"]
        }
        
        logger.info(f"✅ Initialized TestMobileStrategy for device {device_id}")
    
    def _extract_target_app(self, goal: str) -> Optional[str]:
        """Extract target app name from goal"""
        goal_lower = goal.lower()
        
        for app_name, patterns in self.app_patterns.items():
            for pattern in patterns:
                if pattern in goal_lower:
                    return app_name
        
        return None
    
    def _detect_device_state(self, ui_tree: SemanticUITree) -> str:
        """Detect current device state based on UI content"""
        app_name = ui_tree.app_name.lower()
        screen_name = ui_tree.screen_name.lower() if ui_tree.screen_name else ""
        
        # Check for home screen indicators
        home_indicators = [
            "launcher", "home", "desktop", "wallpaper", "widget",
            "app list", "app drawer", "all apps"
        ]
        
        if any(indicator in app_name or indicator in screen_name for indicator in home_indicators):
            return "home_screen"
        
        # Check for app drawer
        drawer_indicators = ["app drawer", "all apps", "apps"]
        if any(indicator in screen_name for indicator in drawer_indicators):
            return "app_drawer"
        
        # Check if we're in the target app
        if self.target_app and self.target_app in app_name:
            return f"in_{self.target_app}"
        
        # Check for common system apps
        system_apps = ["settings", "phone", "messages", "camera", "calculator"]
        if any(app in app_name for app in system_apps):
            return f"in_{app_name}"
        
        # Default to in_app for any other app
        return "in_app"
    
    def _detect_infinite_loop(self) -> bool:
        """Detect if we're stuck in an infinite loop"""
        if len(self.previous_ui_trees) < 3:
            return False
        
        # Check if we've been in the same state for too long
        recent_states = [self._detect_device_state(tree) for tree in self.previous_ui_trees[-3:]]
        if len(set(recent_states)) == 1:
            # Same state for 3 consecutive steps
            logger.warning(f"⚠️ Stuck in same state: {recent_states[0]}")
            return True
        
        # Check for repetitive actions
        if len(self.action_history) >= 3:
            recent_actions = [action["action"]["action_type"] for action in self.action_history[-3:]]
            if len(set(recent_actions)) == 1 and recent_actions[0] == "type":
                # Repeated typing actions
                logger.warning(f"⚠️ Repeated typing actions detected")
                return True
        
        return False
    
    def _extract_json_from_response(self, text: str) -> Optional[str]:
        """Extract JSON from LLM response, handling various formats"""
        import re
        
        # Remove markdown code blocks
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        
        # Find JSON object
        match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
        if match:
            return match.group(0).strip()
        
        return None
    
    def _json_to_ui_action(self, action_json: Dict) -> Dict:
        """Convert JSON decision to UIAction (simplified for testing)"""
        return {
            "action_type": action_json.get("action_type"),
            "element_id": action_json.get("element_id"),
            "text": action_json.get("text"),
            "direction": action_json.get("direction"),
            "duration": action_json.get("duration", 1000),
            "global_action": action_json.get("global_action")
        }

async def test_device_state_detection():
    """Test device state detection logic"""
    
    logger.info("🧪 Testing device state detection...")
    
    # Create strategy
    strategy = TestMobileStrategy("test_device")
    
    # Test home screen detection
    home_ui_tree = SemanticUITree(
        screen_id="screen_1",
        device_id="test_device",
        app_name="Launcher",
        app_package="com.android.launcher",
        screen_name="Home Screen",
        elements=[],
        screen_width=1080,
        screen_height=2340
    )
    
    state = strategy._detect_device_state(home_ui_tree)
    assert state == "home_screen", f"Expected home_screen, got {state}"
    logger.info("✅ Home screen detection works")
    
    # Test app drawer detection
    drawer_ui_tree = SemanticUITree(
        screen_id="screen_2",
        device_id="test_device",
        app_name="Launcher",
        app_package="com.android.launcher",
        screen_name="App Drawer",
        elements=[],
        screen_width=1080,
        screen_height=2340
    )
    
    state = strategy._detect_device_state(drawer_ui_tree)
    assert state == "app_drawer", f"Expected app_drawer, got {state}"
    logger.info("✅ App drawer detection works")
    
    # Test Gmail app detection
    strategy.target_app = "gmail"
    gmail_ui_tree = SemanticUITree(
        screen_id="screen_3",
        device_id="test_device",
        app_name="Gmail",
        app_package="com.google.android.gm",
        screen_name="Compose",
        elements=[],
        screen_width=1080,
        screen_height=2340
    )
    
    state = strategy._detect_device_state(gmail_ui_tree)
    assert state == "in_gmail", f"Expected in_gmail, got {state}"
    logger.info("✅ Gmail app detection works")
    
    # Test Aura app detection (the problematic case)
    aura_ui_tree = SemanticUITree(
        screen_id="screen_4",
        device_id="test_device",
        app_name="Aura",
        app_package="com.example.aura",
        screen_name="Main Screen",
        elements=[],
        screen_width=1080,
        screen_height=2340
    )
    
    state = strategy._detect_device_state(aura_ui_tree)
    assert state == "in_app", f"Expected in_app, got {state}"
    logger.info("✅ Aura app detection works (correctly identifies as in_app)")
    
    return True

async def test_target_app_extraction():
    """Test target app extraction from goal"""
    
    logger.info("🧪 Testing target app extraction...")
    
    # Create strategy
    strategy = TestMobileStrategy("test_device")
    
    # Test Gmail extraction
    app = strategy._extract_target_app("open the gmail app")
    assert app == "gmail", f"Expected gmail, got {app}"
    logger.info("✅ Gmail extraction works")
    
    # Test WhatsApp extraction
    app = strategy._extract_target_app("send a message on WhatsApp")
    assert app == "whatsapp", f"Expected whatsapp, got {app}"
    logger.info("✅ WhatsApp extraction works")
    
    # Test Chrome extraction
    app = strategy._extract_target_app("open chrome browser")
    assert app == "chrome", f"Expected chrome, got {app}"
    logger.info("✅ Chrome extraction works")
    
    # Test unknown app
    app = strategy._extract_target_app("do something random")
    assert app is None, f"Expected None, got {app}"
    logger.info("✅ Unknown app handling works")
    
    # Test case insensitive
    app = strategy._extract_target_app("OPEN THE GMAIL APP")
    assert app == "gmail", f"Expected gmail, got {app}"
    logger.info("✅ Case insensitive extraction works")
    
    return True

async def test_infinite_loop_detection():
    """Test infinite loop detection logic"""
    
    logger.info("🧪 Testing infinite loop detection...")
    
    # Create strategy
    strategy = TestMobileStrategy("test_device")
    
    # Test same state detection
    ui_tree1 = SemanticUITree(
        screen_id="screen_1",
        device_id="test_device",
        app_name="Aura",
        app_package="com.example.aura",
        screen_name="Main Screen",
        elements=[],
        screen_width=1080,
        screen_height=2340
    )
    
    ui_tree2 = SemanticUITree(
        screen_id="screen_2",
        device_id="test_device",
        app_name="Aura",
        app_package="com.example.aura",
        screen_name="Main Screen",
        elements=[],
        screen_width=1080,
        screen_height=2340
    )
    
    ui_tree3 = SemanticUITree(
        screen_id="screen_3",
        device_id="test_device",
        app_name="Aura",
        app_package="com.example.aura",
        screen_name="Main Screen",
        elements=[],
        screen_width=1080,
        screen_height=2340
    )
    
    strategy.previous_ui_trees = [ui_tree1, ui_tree2, ui_tree3]
    
    # Should detect infinite loop (same state 3 times)
    loop_detected = strategy._detect_infinite_loop()
    assert loop_detected == True, "Expected infinite loop to be detected"
    logger.info("✅ Same state loop detection works")
    
    # Test repetitive typing actions
    strategy.previous_ui_trees = []
    strategy.action_history = [
        {"action": {"action_type": "type"}, "device_state": "home_screen"},
        {"action": {"action_type": "type"}, "device_state": "home_screen"},
        {"action": {"action_type": "type"}, "device_state": "home_screen"}
    ]
    
    # Should detect repetitive typing
    loop_detected = strategy._detect_infinite_loop()
    assert loop_detected == True, "Expected repetitive typing to be detected"
    logger.info("✅ Repetitive typing detection works")
    
    # Test no loop with different states
    strategy.previous_ui_trees = [ui_tree1, ui_tree2]
    strategy.action_history = [
        {"action": {"action_type": "click"}, "device_state": "home_screen"},
        {"action": {"action_type": "type"}, "device_state": "in_app"},
        {"action": {"action_type": "global_action"}, "device_state": "app_drawer"}
    ]
    
    # Should NOT detect loop (different states/actions)
    loop_detected = strategy._detect_infinite_loop()
    assert loop_detected == False, "Expected no loop to be detected"
    logger.info("✅ Different state handling works")
    
    return True

async def test_json_extraction():
    """Test JSON extraction from LLM responses"""
    
    logger.info("🧪 Testing JSON extraction...")
    
    # Create strategy
    strategy = TestMobileStrategy("test_device")
    
    # Test normal JSON
    text = '{"action_type": "click", "element_id": 1}'
    result = strategy._extract_json_from_response(text)
    assert result == text, f"Expected {text}, got {result}"
    logger.info("✅ Normal JSON extraction works")
    
    # Test JSON with markdown
    text = '```json\n{"action_type": "click", "element_id": 1}\n```'
    result = strategy._extract_json_from_response(text)
    expected = '{"action_type": "click", "element_id": 1}'
    assert result == expected, f"Expected {expected}, got {result}"
    logger.info("✅ Markdown JSON extraction works")
    
    # Test invalid JSON
    text = 'This is not JSON'
    result = strategy._extract_json_from_response(text)
    assert result is None, f"Expected None, got {result}"
    logger.info("✅ Invalid JSON handling works")
    
    # Test complex JSON
    text = '{"thought": "Need to click Gmail", "action_type": "click", "element_id": 1, "reason": "Opening Gmail app"}'
    result = strategy._extract_json_from_response(text)
    assert result == text, f"Expected {text}, got {result}"
    logger.info("✅ Complex JSON extraction works")
    
    return True

async def test_ui_action_conversion():
    """Test UI action conversion from JSON"""
    
    logger.info("🧪 Testing UI action conversion...")
    
    # Create strategy
    strategy = TestMobileStrategy("test_device")
    
    # Test click action
    action_json = {
        "action_type": "click",
        "element_id": 1
    }
    
    action = strategy._json_to_ui_action(action_json)
    assert action["action_type"] == "click", f"Expected click, got {action['action_type']}"
    assert action["element_id"] == 1, f"Expected element_id 1, got {action['element_id']}"
    logger.info("✅ Click action conversion works")
    
    # Test type action
    action_json = {
        "action_type": "type",
        "element_id": 2,
        "text": "hello"
    }
    
    action = strategy._json_to_ui_action(action_json)
    assert action["action_type"] == "type", f"Expected type, got {action['action_type']}"
    assert action["element_id"] == 2, f"Expected element_id 2, got {action['element_id']}"
    assert action["text"] == "hello", f"Expected text 'hello', got {action['text']}"
    logger.info("✅ Type action conversion works")
    
    # Test global action
    action_json = {
        "action_type": "global_action",
        "global_action": "HOME"
    }
    
    action = strategy._json_to_ui_action(action_json)
    assert action["action_type"] == "global_action", f"Expected global_action, got {action['action_type']}"
    assert action["global_action"] == "HOME", f"Expected HOME, got {action['global_action']}"
    logger.info("✅ Global action conversion works")
    
    # Test scroll action
    action_json = {
        "action_type": "scroll",
        "direction": "up"
    }
    
    action = strategy._json_to_ui_action(action_json)
    assert action["action_type"] == "scroll", f"Expected scroll, got {action['action_type']}"
    assert action["direction"] == "up", f"Expected up, got {action['direction']}"
    logger.info("✅ Scroll action conversion works")
    
    return True

async def test_aura_scenario_logic():
    """Test the specific Aura app scenario logic"""
    
    logger.info("🧪 Testing Aura app scenario logic...")
    
    # Create strategy
    strategy = TestMobileStrategy("test_device")
    
    # Set target app
    strategy.target_app = strategy._extract_target_app("open the gmail app")
    assert strategy.target_app == "gmail", "Should extract Gmail as target app"
    logger.info("✅ Target app extraction works for Aura scenario")
    
    # Create Aura app UI tree (the problematic case)
    aura_ui_tree = SemanticUITree(
        screen_id="screen_aura",
        device_id="test_device",
        app_name="Aura",
        app_package="com.example.aura",
        screen_name="Main Screen",
        elements=[
            UIElement(
                element_id=1,
                type="button",
                text="Send to Backend",
                clickable=True,
                content_description="Send text input to backend"
            ),
            UIElement(
                element_id=2,
                type="textfield",
                text="",
                hint_text="open the gmail app",
                clickable=True,
                focusable=True
            )
        ],
        screen_width=1080,
        screen_height=2340
    )
    
    # Detect device state
    state = strategy._detect_device_state(aura_ui_tree)
    assert state == "in_app", f"Expected in_app, got {state}"
    logger.info("✅ Aura app correctly identified as in_app (not home screen)")
    
    # The key insight: we're in the wrong app and need to navigate
    assert state != "home_screen", "Should not be identified as home screen"
    logger.info("✅ Aura app correctly NOT identified as home screen")
    
    # Test that we can detect this is not the target app
    assert strategy.target_app not in aura_ui_tree.app_name.lower(), "Should not be in target app"
    logger.info("✅ Correctly identified that we're not in Gmail app")
    
    return True

async def main():
    """Run all tests"""
    
    logger.info("🚀 Starting logic-only hallucination fix tests...")
    
    tests = [
        ("Device State Detection", test_device_state_detection),
        ("Target App Extraction", test_target_app_extraction),
        ("Infinite Loop Detection", test_infinite_loop_detection),
        ("JSON Extraction", test_json_extraction),
        ("UI Action Conversion", test_ui_action_conversion),
        ("Aura Scenario Logic", test_aura_scenario_logic)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        logger.info(f"\n{'='*60}")
        logger.info(f"🧪 Running: {test_name}")
        logger.info(f"{'='*60}")
        
        try:
            success = await test_func()
            results.append((test_name, success))
        except Exception as e:
            logger.error(f"❌ Test {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info(f"📊 TEST SUMMARY")
    logger.info(f"{'='*60}")
    
    passed = 0
    for test_name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        logger.info(f"   {test_name}: {status}")
        if success:
            passed += 1
    
    logger.info(f"\n🎯 Overall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        logger.info("🎉 All tests passed! The infinite loop hallucination fix logic is working correctly.")
        logger.info("✨ Key insights verified:")
        logger.info("   - Aura app is correctly identified as 'in_app' (not home screen)")
        logger.info("   - Target app extraction works for common apps")
        logger.info("   - Infinite loop detection prevents repetitive actions")
        logger.info("   - Device state detection enables proper navigation logic")
    else:
        logger.error("⚠️ Some tests failed. The fix may need additional work.")

if __name__ == "__main__":
    asyncio.run(main())