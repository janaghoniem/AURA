#!/usr/bin/env python3
"""
Quick test to verify task completion detection is working
"""

import asyncio
from agents.execution_agent.strategies.mobile_strategy import MobileStrategy
from agents.utils.device_protocol import SemanticUITree, UIElement

async def test_completion_detection():
    """Test the _check_task_completion method"""
    
    strategy = MobileStrategy(device_id="test_device")
    
    # Simulate Gmail app UI
    gmail_ui = SemanticUITree(
        timestamp="2026-01-24T16:00:00Z",
        device_id="test_device",
        elements=[
            UIElement(id=1, type="Button", text="Compose", clickable=True, focusable=False, bounds=[0,0,100,50], visibility="visible", content_desc="Compose email"),
            UIElement(id=2, type="Button", text="Inbox", clickable=True, focusable=False, bounds=[0,50,100,100], visibility="visible", content_desc="Your inbox"),
            UIElement(id=3, type="Text", text="5 unread emails", clickable=False, focusable=False, bounds=[0,100,300,150], visibility="visible", content_desc=""),
            UIElement(id=4, type="List", text="emails", clickable=False, focusable=False, bounds=[0,150,400,600], visibility="visible", content_desc="List of emails"),
        ]
    )
    
    chrome_ui = SemanticUITree(
        timestamp="2026-01-24T16:00:00Z",
        device_id="test_device",
        elements=[
            UIElement(id=1, type="Button", text="https://www.google.com", clickable=True, focusable=False, bounds=[0,0,400,50], visibility="visible", content_desc="URL bar"),
            UIElement(id=2, type="Text", text="Search or type URL", clickable=False, focusable=False, bounds=[0,50,400,100], visibility="visible", content_desc=""),
            UIElement(id=3, type="List", text="Search results", clickable=False, focusable=False, bounds=[0,100,400,600], visibility="visible", content_desc=""),
        ]
    )
    
    settings_ui = SemanticUITree(
        timestamp="2026-01-24T16:00:00Z",
        device_id="test_device",
        elements=[
            UIElement(id=1, type="Text", text="Device Settings", clickable=False, focusable=False, bounds=[0,0,300,50], visibility="visible", content_desc=""),
            UIElement(id=2, type="Button", text="Display", clickable=True, focusable=False, bounds=[0,50,300,100], visibility="visible", content_desc=""),
            UIElement(id=3, type="Button", text="System preferences", clickable=True, focusable=False, bounds=[0,100,300,150], visibility="visible", content_desc=""),
            UIElement(id=4, type="List", text="Settings options", clickable=False, focusable=False, bounds=[0,150,400,600], visibility="visible", content_desc=""),
        ]
    )
    
    # Test cases
    tests = [
        ("Open Gmail app", gmail_ui, True, "App opened: gmail"),
        ("Open Chrome", chrome_ui, True, "App opened: chrome"),
        ("Open Settings", settings_ui, True, "App opened: settings"),
        ("Send an email", gmail_ui, True, "App opened: gmail"),  # Gmail is prerequisite
        ("Unknown app", gmail_ui, False, None),  # Task doesn't mention any app
    ]
    
    print("\n🧪 Testing Task Completion Detection\n")
    print("=" * 70)
    
    passed = 0
    failed = 0
    
    for task_prompt, ui_tree, should_complete, expected_reason in tests:
        result = strategy._check_task_completion(ui_tree, task_prompt)
        
        if should_complete:
            if result:
                status = "✅ PASS"
                passed += 1
            else:
                status = "❌ FAIL"
                failed += 1
                print(f"\n{status}")
                print(f"  Task: {task_prompt}")
                print(f"  Expected completion, got: {result}")
                continue
        else:
            if result is None:
                status = "✅ PASS"
                passed += 1
            else:
                status = "❌ FAIL"
                failed += 1
                print(f"\n{status}")
                print(f"  Task: {task_prompt}")
                print(f"  Expected no completion, got: {result}")
                continue
        
        print(f"{status} | Task: {task_prompt}")
        if result:
            print(f"         Reason: {result}")
    
    print("\n" + "=" * 70)
    print(f"\n📊 Results: {passed} passed, {failed} failed\n")
    
    if failed == 0:
        print("🎉 All tests passed!")
    else:
        print(f"⚠️  {failed} test(s) failed")

if __name__ == "__main__":
    asyncio.run(test_completion_detection())
