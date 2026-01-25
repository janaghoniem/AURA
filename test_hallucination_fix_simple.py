#!/usr/bin/env python3
"""
Simple test script to verify the infinite loop hallucination fix
Tests the logic without requiring external API calls
"""

import asyncio
import json
import logging
from unittest.mock import AsyncMock, MagicMock
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from agents.execution_agent.strategies.mobile_strategy import MobileReActStrategy
from agents.utils.device_protocol import (
    MobileTaskRequest, SemanticUITree, UIElement
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_device_state_detection():
    """Test device state detection logic"""
    
    logger.info("🧪 Testing device state detection...")
    
    # Create strategy
    strategy = MobileReActStrategy("test_device")
    
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
    
    return True

async def test_target_app_extraction():
    """Test target app extraction from goal"""
    
    logger.info("🧪 Testing target app extraction...")
    
    # Create strategy
    strategy = MobileReActStrategy("test_device")
    
    # Test Gmail extraction
    app = strategy._extract_target_app("open the gmail app")
    assert app == "gmail", f"Expected gmail, got {app}"
    logger.info("✅ Gmail extraction works")
    
    # Test WhatsApp extraction
    app = strategy._extract_target_app("send a message on WhatsApp")
    assert app == "whatsapp", f"Expected whatsapp, got {app}"
    logger.info("✅ WhatsApp extraction works")
    
    # Test unknown app
    app = strategy._extract_target_app("do something random")
    assert app is None, f"Expected None, got {app}"
    logger.info("✅ Unknown app handling works")
    
    return True

async def test_infinite_loop_detection():
    """Test infinite loop detection logic"""
    
    logger.info("🧪 Testing infinite loop detection...")
    
    # Create strategy
    strategy = MobileReActStrategy("test_device")
    
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
    
    return True

async def test_json_extraction():
    """Test JSON extraction from LLM responses"""
    
    logger.info("🧪 Testing JSON extraction...")
    
    # Create strategy
    strategy = MobileReActStrategy("test_device")
    
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
    
    return True

async def test_ui_action_conversion():
    """Test UI action conversion from JSON"""
    
    logger.info("🧪 Testing UI action conversion...")
    
    # Create strategy
    strategy = MobileReActStrategy("test_device")
    
    # Test click action
    action_json = {
        "action_type": "click",
        "element_id": 1
    }
    
    action = strategy._json_to_ui_action(action_json)
    assert action.action_type == "click", f"Expected click, got {action.action_type}"
    assert action.element_id == 1, f"Expected element_id 1, got {action.element_id}"
    logger.info("✅ Click action conversion works")
    
    # Test type action
    action_json = {
        "action_type": "type",
        "element_id": 2,
        "text": "hello"
    }
    
    action = strategy._json_to_ui_action(action_json)
    assert action.action_type == "type", f"Expected type, got {action.action_type}"
    assert action.element_id == 2, f"Expected element_id 2, got {action.element_id}"
    assert action.text == "hello", f"Expected text 'hello', got {action.text}"
    logger.info("✅ Type action conversion works")
    
    # Test global action
    action_json = {
        "action_type": "global_action",
        "global_action": "HOME"
    }
    
    action = strategy._json_to_ui_action(action_json)
    assert action.action_type == "global_action", f"Expected global_action, got {action.action_type}"
    assert action.global_action == "HOME", f"Expected HOME, got {action.global_action}"
    logger.info("✅ Global action conversion works")
    
    return True

async def main():
    """Run all tests"""
    
    logger.info("🚀 Starting simple hallucination fix tests...")
    
    tests = [
        ("Device State Detection", test_device_state_detection),
        ("Target App Extraction", test_target_app_extraction),
        ("Infinite Loop Detection", test_infinite_loop_detection),
        ("JSON Extraction", test_json_extraction),
        ("UI Action Conversion", test_ui_action_conversion)
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
    else:
        logger.error("⚠️ Some tests failed. The fix may need additional work.")

if __name__ == "__main__":
    asyncio.run(main())