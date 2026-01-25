#!/usr/bin/env python3
"""Test script to verify compose email task works with the fixes"""
import asyncio
import sys
sys.path.insert(0, '/Users/mohammedwalidadawy/Development/YUSR/backend')

from agents.utils.device_protocol import SemanticUITree, UIElement
from agents.execution_agent.strategies.mobile_strategy import EnhancedMobileReActStrategy

async def test_compose_task():
    """Test compose email task"""
    strategy = EnhancedMobileReActStrategy(
        device_id="android_device_1",
        goal="Compose a new email in Gmail with subject 'Test' and body 'Hello'",
        backend_url="http://localhost:8000",
        timeout_seconds=30
    )
    
    print("\n" + "="*70)
    print("🧪 TESTING COMPOSE EMAIL TASK WITH FIXES")
    print("="*70)
    print("\nChanges made:")
    print("✅ Device state detection now recognizes Chrome Home as in_chrome")
    print("✅ Mock device now returns Compose screen when compose button is clicked")
    print("✅ Mock tracks current app to handle element clicks within apps\n")
    
    try:
        result = await strategy.execute_task()
        print(f"\n✅ Task completed: {result.get('success', False)}")
        if result.get('reason'):
            print(f"   Reason: {result['reason']}")
    except Exception as e:
        print(f"\n❌ Task failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_compose_task())
