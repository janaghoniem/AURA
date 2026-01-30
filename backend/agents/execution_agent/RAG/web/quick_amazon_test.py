"""
Quick Amazon Navigation Test
Tests the improved navigation logic with fallback strategies
Place in: backend/agents/execution_agent/RAG/web/
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_amazon_quick():
    """Quick test of Amazon navigation with new fallback logic"""
    
    print("="*80)
    print("🚀 QUICK AMAZON NAVIGATION TEST")
    print("="*80)
    
    from web_execution import WebExecutionPipeline, WebExecutionConfig
    
    # Create config with increased timeouts
    config = WebExecutionConfig(
        headless=False,
        timeout_seconds=60,
        max_navigation_time=60000
        
    )
    
    pipeline = WebExecutionPipeline(config)
    
    try:
        print("\n📍 Initializing browser...")
        await pipeline.initialize()
        print("✅ Browser initialized")
        
        # Test navigation with networkidle (will fallback automatically)
        print("\n🔗 Testing navigation with 'networkidle' (should fallback)...")
        nav_task = {
            'task_id': 'test_nav',
            'ai_prompt': 'Navigate to Amazon',
            'web_params': {
                'url': 'https://www.amazon.com',
                'action': 'navigate',
                'wait_for': 'networkidle'  # Will trigger fallback
            }
        }
        
        result = await pipeline.execute_web_task(nav_task, 'test_session')
        
        if result.validation_passed:
            print("✅ NAVIGATION SUCCESSFUL!")
            print(f"   Status: {result.status.value}")
            print(f"   Output: {result.output[:100]}...")
            
            # Wait a bit to see the page
            print("\n👀 Keeping browser open for 5 seconds...")
            await asyncio.sleep(5)
        else:
            print("❌ NAVIGATION FAILED")
            print(f"   Error: {result.error}")
            print(f"   Validation errors: {result.validation_errors}")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("\n🔒 Cleaning up...")
        await pipeline.cleanup()
        print("✅ Done!")

if __name__ == "__main__":
    asyncio.run(test_amazon_quick())