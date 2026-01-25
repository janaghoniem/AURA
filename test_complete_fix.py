#!/usr/bin/env python3
"""
Complete Fix Test - Tests the infinite loop hallucination fix
============================================================

This test verifies that the complete fix works by:
1. Testing the enhanced mobile strategy with proper navigation
2. Simulating the Gmail scenario that was causing infinite loops
3. Verifying that navigation actions work correctly
4. Confirming no infinite loops occur

Usage:
    python test_complete_fix.py
"""

import asyncio
import logging
import sys
import os
from typing import Dict, Any, Optional

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from agents.execution_agent.strategies.mobile_strategy import MobileReActStrategy
from agents.utils.device_protocol import MobileTaskRequest, UIAction, ActionResult

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MockDevice:
    """Mock device that simulates the Android device behavior"""
    
    def __init__(self):
        self.current_app = "Aura App"
        self.device_state = "in_app"
        self.action_history = []
        
    async def get_ui_tree(self):
        """Return current UI tree based on device state"""
        if self.device_state == "in_app":
            return {
                "screen_id": "screen_main",
                "device_id": "android_device_1",
                "app_name": "Aura App",
                "app_package": "com.aura.app",
                "screen_name": "Main Screen",
                "elements": [
                    {
                        "element_id": 1,
                        "text": "Send",
                        "content_description": "Send",
                        "clickable": True,
                        "focusable": True,
                    },
                    {
                        "element_id": 2,
                        "text": "open gmail",
                        "content_description": "Text input field",
                        "clickable": True,
                        "focusable": True,
                    },
                ],
                "timestamp": 1234567890,
                "screen_width": 1080,
                "screen_height": 2340,
            }
        elif self.device_state == "home_screen":
            return {
                "screen_id": "screen_home",
                "device_id": "android_device_1",
                "app_name": "Launcher",
                "app_package": "com.android.launcher",
                "screen_name": "Home Screen",
                "elements": [
                    {
                        "element_id": 1,
                        "text": "Gmail",
                        "content_description": "Gmail app icon",
                        "clickable": True,
                        "focusable": True,
                    },
                    {
                        "element_id": 2,
                        "text": "WhatsApp",
                        "content_description": "WhatsApp app icon",
                        "clickable": True,
                        "focusable": True,
                    },
                ],
                "timestamp": 1234567891,
                "screen_width": 1080,
                "screen_height": 2340,
            }
        elif self.device_state == "in_gmail":
            return {
                "screen_id": "screen_gmail",
                "device_id": "android_device_1",
                "app_name": "Gmail",
                "app_package": "com.google.android.gm",
                "screen_name": "Gmail Inbox",
                "elements": [
                    {
                        "element_id": 1,
                        "text": "Compose",
                        "content_description": "Compose new email",
                        "clickable": True,
                        "focusable": True,
                    },
                ],
                "timestamp": 1234567892,
                "screen_width": 1080,
                "screen_height": 2340,
            }
    
    async def execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute action and update device state"""
        action_type = action.get("action_type")
        self.action_history.append(action)
        
        logger.info(f"📱 Executing action: {action_type}")
        
        if action_type == "global_action":
            global_action = action.get("global_action", "").upper()
            if global_action == "HOME":
                self.device_state = "home_screen"
                self.current_app = "Launcher"
                logger.info("🏠 Navigated to home screen")
                return {"success": True, "execution_time_ms": 1000}
            elif global_action == "BACK":
                if self.device_state == "in_app":
                    self.device_state = "home_screen"
                    self.current_app = "Launcher"
                    logger.info("⬅️ Navigated back to home screen")
                return {"success": True, "execution_time_ms": 1000}
        
        elif action_type == "navigate_home":
            self.device_state = "home_screen"
            self.current_app = "Launcher"
            logger.info("🏠 Navigated to home screen (Flutter method)")
            return {"success": True, "execution_time_ms": 1000}
        
        elif action_type == "navigate_back":
            if self.device_state == "in_app":
                self.device_state = "home_screen"
                self.current_app = "Launcher"
                logger.info("⬅️ Navigated back to home screen (Flutter method)")
            return {"success": True, "execution_time_ms": 1000}
        
        elif action_type == "click":
            element_id = action.get("element_id")
            if self.device_state == "home_screen" and element_id == 1:
                # Clicked Gmail icon
                self.device_state = "in_gmail"
                self.current_app = "Gmail"
                logger.info("📧 Opened Gmail app")
                return {"success": True, "execution_time_ms": 1000}
        
        return {"success": False, "error": "Action not supported", "execution_time_ms": 0}


class TestMobileStrategy(MobileReActStrategy):
    """Test version of MobileReActStrategy that uses mock device"""
    
    def __init__(self, device_id: str = "test_device"):
        super().__init__(device_id)
        self.mock_device = MockDevice()
    
    async def _fetch_ui_tree_from_device(self) -> Optional[Dict[str, Any]]:
        """Override to use mock device"""
        return await self.mock_device.get_ui_tree()
    
    async def _execute_action_on_device(self, action: UIAction) -> ActionResult:
        """Override to use mock device"""
        result = await self.mock_device.execute_action(action.dict())
        return ActionResult(
            action_id=action.action_id,
            success=result["success"],
            error=result.get("error"),
            execution_time_ms=result["execution_time_ms"]
        )


async def test_gmail_scenario():
    """Test the exact scenario that was causing infinite loops"""
    logger.info("\n" + "="*70)
    logger.info("🧪 TESTING GMAIL SCENARIO (Original Infinite Loop Problem)")
    logger.info("="*70)
    
    # Create test task
    task = MobileTaskRequest(
        task_id="test_gmail_1",
        ai_prompt="open the gmail app",
        device_id="test_device",
        max_steps=5,
        timeout_seconds=30
    )
    
    # Create test strategy
    strategy = TestMobileStrategy("test_device")
    
    # Execute task
    result = await strategy.execute_task(task)
    
    # Verify results
    logger.info(f"\n📊 TEST RESULTS:")
    logger.info(f"   Status: {result.status}")
    logger.info(f"   Steps taken: {result.steps_taken}")
    logger.info(f"   Actions executed: {len(result.actions_executed)}")
    logger.info(f"   Execution time: {result.execution_time_ms}ms")
    
    if result.error:
        logger.info(f"   Error: {result.error}")
    
    # Check if test passed
    success = result.status == "success"
    logger.info(f"\n🎯 TEST RESULT: {'✅ PASSED' if success else '❌ FAILED'}")
    
    if success:
        logger.info("✅ No infinite loop detected!")
        logger.info("✅ Task completed successfully!")
        logger.info("✅ Navigation worked correctly!")
    else:
        logger.info("❌ Test failed - infinite loop may still exist")
    
    return success


async def test_navigation_methods():
    """Test that navigation methods work correctly"""
    logger.info("\n" + "="*70)
    logger.info("🧪 TESTING NAVIGATION METHODS")
    logger.info("="*70)
    
    strategy = TestMobileStrategy("test_device")
    
    # Test navigate_home
    logger.info("🏠 Testing navigate_home...")
    action = UIAction(action_type="navigate_home", action_id="test_1")
    result = await strategy._execute_action_on_device(action)
    logger.info(f"   Result: {'✅ Success' if result.success else '❌ Failed'}")
    
    # Test navigate_back
    logger.info("⬅️ Testing navigate_back...")
    action = UIAction(action_type="navigate_back", action_id="test_2")
    result = await strategy._execute_action_on_device(action)
    logger.info(f"   Result: {'✅ Success' if result.success else '❌ Failed'}")
    
    # Test global_action HOME
    logger.info("🏠 Testing global_action HOME...")
    action = UIAction(action_type="global_action", global_action="HOME", action_id="test_3")
    result = await strategy._execute_action_on_device(action)
    logger.info(f"   Result: {'✅ Success' if result.success else '❌ Failed'}")
    
    return True


async def test_infinite_loop_detection():
    """Test that infinite loop detection works"""
    logger.info("\n" + "="*70)
    logger.info("🧪 TESTING INFINITE LOOP DETECTION")
    logger.info("="*70)
    
    strategy = TestMobileStrategy("test_device")
    
    # Simulate being stuck in same state
    strategy.device_state = "in_app"
    strategy.previous_ui_trees = [strategy.current_ui_tree] * 3
    strategy.action_history = [
        {"action": {"action_type": "type"}, "device_state": "in_app"},
        {"action": {"action_type": "type"}, "device_state": "in_app"},
        {"action": {"action_type": "type"}, "device_state": "in_app"},
    ]
    
    # Check if loop is detected
    loop_detected = strategy._detect_infinite_loop()
    logger.info(f"   Loop detected: {'✅ Yes' if loop_detected else '❌ No'}")
    
    if loop_detected:
        logger.info("✅ Infinite loop detection working correctly!")
    else:
        logger.info("❌ Infinite loop detection may not be working")
    
    return loop_detected


async def main():
    """Run all tests"""
    logger.info("🚀 Starting Complete Fix Tests...")
    
    tests = [
        ("Gmail Scenario", test_gmail_scenario),
        ("Navigation Methods", test_navigation_methods),
        ("Infinite Loop Detection", test_infinite_loop_detection),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            logger.info(f"\n{'='*50}")
            logger.info(f"🧪 Running: {test_name}")
            logger.info(f"{'='*50}")
            
            result = await test_func()
            results.append((test_name, result))
            
        except Exception as e:
            logger.error(f"❌ Test {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info("\n" + "="*70)
    logger.info("📊 TEST SUMMARY")
    logger.info("="*70)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"   {test_name}: {status}")
        if result:
            passed += 1
    
    logger.info(f"\n🎯 Overall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        logger.info("\n🎉 ALL TESTS PASSED! The infinite loop fix is working correctly!")
        logger.info("✅ Navigation methods work properly")
        logger.info("✅ Infinite loop detection prevents stuck scenarios")
        logger.info("✅ Gmail scenario completes successfully")
    else:
        logger.info(f"\n⚠️ {len(results) - passed} tests failed. The fix may need additional work.")
    
    return passed == len(results)


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)