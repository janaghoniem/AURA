#!/usr/bin/env python3
"""
Test script to verify the infinite loop hallucination fix
Tests the "open the gmail app" scenario that was causing infinite loops
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

class MockLLMClient:
    """Mock LLM client for testing"""
    
    def __init__(self):
        self.responses = []
    
    async def chat(self):
        return self
    
    async def completions(self):
        return self
    
    async def create(self, model, messages, temperature, max_tokens):
        """Mock LLM response based on the current UI state"""
        
        # Get the current UI state from the last message
        user_message = messages[1]["content"]
        
        # Mock responses based on different scenarios
        if "Main Screen" in user_message and "Send to Backend" in user_message:
            # This is the problematic scenario - Aura app with text field
            response = {
                "choices": [{
                    "message": {
                        "content": json.dumps({
                            "thought": "We're in the Aura app, not on the home screen. We need to navigate back to the home screen to open Gmail.",
                            "action_type": "global_action",
                            "global_action": "HOME",
                            "reason": "Need to exit Aura app and go to home screen"
                        })
                    }
                }]
            }
        elif "Home Screen" in user_message and "Gmail" in user_message:
            # Home screen with Gmail app visible
            response = {
                "choices": [{
                    "message": {
                        "content": json.dumps({
                            "thought": "Gmail app is visible on home screen, clicking it to open",
                            "action_type": "click",
                            "element_id": 1,
                            "reason": "Opening Gmail app from home screen"
                        })
                    }
                }]
            }
        elif "Gmail" in user_message and "Compose" in user_message:
            # Gmail app is open
            response = {
                "choices": [{
                    "message": {
                        "content": json.dumps({
                            "thought": "Gmail app is already open, goal achieved",
                            "action_type": "complete",
                            "reason": "Gmail app is successfully opened"
                        })
                    }
                }]
            }
        else:
            # Default response
            response = {
                "choices": [{
                    "message": {
                        "content": json.dumps({
                            "thought": "Need to navigate to home screen first",
                            "action_type": "global_action",
                            "global_action": "HOME",
                            "reason": "Need to exit current app"
                        })
                    }
                }]
            }
        
        return MagicMock(**response)

async def test_aura_app_scenario():
    """Test the specific scenario that was causing infinite loops"""
    
    logger.info("🧪 Testing Aura app infinite loop scenario...")
    
    # Create mock LLM client
    mock_llm = MockLLMClient()
    
    # Create strategy with mock
    strategy = MobileReActStrategy("test_device")
    strategy.llm_client = mock_llm
    
    # Create the problematic UI tree (Aura app with text field)
    aura_ui_tree = SemanticUITree(
        screen_id="screen_123",
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
    
    # Mock the UI tree fetching
    strategy._fetch_ui_tree_from_device = AsyncMock(return_value=aura_ui_tree)
    
    # Mock action execution
    strategy._execute_action_on_device = AsyncMock(return_value=MagicMock(success=True))
    
    # Create task
    task = MobileTaskRequest(
        task_id="test_task_1",
        ai_prompt="open the gmail app",
        device_id="test_device",
        session_id="test_session",
        max_steps=5,
        timeout_seconds=30
    )
    
    # Execute task
    result = await strategy.execute_task(task)
    
    logger.info(f"📊 Test Result:")
    logger.info(f"   Status: {result.status}")
    logger.info(f"   Steps taken: {result.steps_taken}")
    logger.info(f"   Actions executed: {len(result.actions_executed)}")
    
    # Verify the fix worked
    if result.status == "success":
        logger.info("✅ SUCCESS: Task completed without infinite loop!")
        return True
    elif result.status == "failed" and "Infinite loop detected" in str(result.error):
        logger.info("✅ SUCCESS: Infinite loop was detected and prevented!")
        return True
    else:
        logger.error("❌ FAILED: Task did not complete successfully")
        return False

async def test_home_screen_scenario():
    """Test normal home screen scenario"""
    
    logger.info("🧪 Testing normal home screen scenario...")
    
    # Create mock LLM client
    mock_llm = MockLLMClient()
    
    # Create strategy with mock
    strategy = MobileReActStrategy("test_device")
    strategy.llm_client = mock_llm
    
    # Create home screen UI tree with Gmail app
    home_ui_tree = SemanticUITree(
        screen_id="screen_456",
        device_id="test_device",
        app_name="Launcher",
        app_package="com.android.launcher",
        screen_name="Home Screen",
        elements=[
            UIElement(
                element_id=1,
                type="button",
                text="Gmail",
                clickable=True,
                content_description="Gmail app icon"
            ),
            UIElement(
                element_id=2,
                type="button",
                text="Chrome",
                clickable=True,
                content_description="Chrome app icon"
            )
        ],
        screen_width=1080,
        screen_height=2340
    )
    
    # Mock the UI tree fetching
    strategy._fetch_ui_tree_from_device = AsyncMock(return_value=home_ui_tree)
    
    # Mock action execution
    strategy._execute_action_on_device = AsyncMock(return_value=MagicMock(success=True))
    
    # Create task
    task = MobileTaskRequest(
        task_id="test_task_2",
        ai_prompt="open the gmail app",
        device_id="test_device",
        session_id="test_session",
        max_steps=5,
        timeout_seconds=30
    )
    
    # Execute task
    result = await strategy.execute_task(task)
    
    logger.info(f"📊 Test Result:")
    logger.info(f"   Status: {result.status}")
    logger.info(f"   Steps taken: {result.steps_taken}")
    logger.info(f"   Actions executed: {len(result.actions_executed)}")
    
    # Verify the fix worked
    if result.status == "success":
        logger.info("✅ SUCCESS: Gmail app opened from home screen!")
        return True
    else:
        logger.error("❌ FAILED: Task did not complete successfully")
        return False

async def test_infinite_loop_detection():
    """Test that infinite loops are properly detected"""
    
    logger.info("🧪 Testing infinite loop detection...")
    
    # Create mock LLM client that always returns the same problematic response
    class ProblematicLLMClient:
        async def chat(self):
            return self
        
        async def completions(self):
            return self
        
        async def create(self, model, messages, temperature, max_tokens):
            # Always return the same problematic response (typing into text field)
            response = {
                "choices": [{
                    "message": {
                        "content": json.dumps({
                            "thought": "Need to type 'open the gmail app' into the text field",
                            "action_type": "type",
                            "element_id": 2,
                            "text": "open the gmail app",
                            "reason": "Typing command into text field"
                        })
                    }
                }]
            }
            return MagicMock(**response)
    
    # Create strategy with problematic LLM
    strategy = MobileReActStrategy("test_device")
    strategy.llm_client = ProblematicLLMClient()
    
    # Create the problematic UI tree (Aura app with text field)
    aura_ui_tree = SemanticUITree(
        screen_id="screen_789",
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
    
    # Mock the UI tree fetching to always return the same tree
    strategy._fetch_ui_tree_from_device = AsyncMock(return_value=aura_ui_tree)
    
    # Mock action execution
    strategy._execute_action_on_device = AsyncMock(return_value=MagicMock(success=True))
    
    # Create task
    task = MobileTaskRequest(
        task_id="test_task_3",
        ai_prompt="open the gmail app",
        device_id="test_device",
        session_id="test_session",
        max_steps=10,  # Give it more steps to trigger loop detection
        timeout_seconds=30
    )
    
    # Execute task
    result = await strategy.execute_task(task)
    
    logger.info(f"📊 Test Result:")
    logger.info(f"   Status: {result.status}")
    logger.info(f"   Steps taken: {result.steps_taken}")
    logger.info(f"   Error: {result.error}")
    
    # Verify infinite loop was detected
    if result.status == "failed" and "Infinite loop detected" in str(result.error):
        logger.info("✅ SUCCESS: Infinite loop was properly detected and prevented!")
        return True
    else:
        logger.error("❌ FAILED: Infinite loop was not detected")
        return False

async def main():
    """Run all tests"""
    
    logger.info("🚀 Starting hallucination fix tests...")
    
    tests = [
        ("Aura App Scenario", test_aura_app_scenario),
        ("Home Screen Scenario", test_home_screen_scenario),
        ("Infinite Loop Detection", test_infinite_loop_detection)
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
        logger.info("🎉 All tests passed! The infinite loop hallucination fix is working correctly.")
    else:
        logger.error("⚠️ Some tests failed. The fix may need additional work.")

if __name__ == "__main__":
    asyncio.run(main())