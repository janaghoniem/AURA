#!/usr/bin/env python3
# ============================================================================
# WEB AUTOMATION TEST SUITE
# ============================================================================
# Comprehensive tests for all web automation components

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

# Load environment variables
try:
    from dotenv import load_dotenv
    # Try loading from project root (5 levels up from web folder)
    project_root = Path(__file__).parent.parent.parent.parent.parent
    env_file = project_root / '.env'
    
    if env_file.exists():
        load_dotenv(env_file)
        print(f"✅ Loaded .env from: {env_file}")
    else:
        print(f"⚠️  No .env file found at: {env_file}")
        print(f"   Using system environment variables")
except ImportError:
    print("⚠️  python-dotenv not installed, install with: pip install python-dotenv")
except Exception as e:
    print(f"⚠️  Could not load .env: {e}")

# ============================================================================
# TEST 1: Playwright Browser Launch
# ============================================================================

async def test_browser_launch():
    """Test basic Playwright browser functionality"""
    print("\n" + "=" * 80)
    print("TEST 1: Playwright Browser Launch")
    print("=" * 80)
    
    try:
        from web_execution import WebExecutionPipeline, WebExecutionConfig
        
        config = WebExecutionConfig(
            headless=False,  # Show browser
            timeout_seconds=10
        )
        
        pipeline = WebExecutionPipeline(config)
        await pipeline.initialize()
        
        print("✅ Browser launched successfully")
        
        await pipeline.cleanup()
        print("✅ Browser closed successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

# ============================================================================
# TEST 2: Basic Navigation
# ============================================================================

async def test_basic_navigation():
    """Test navigating to a webpage"""
    print("\n" + "=" * 80)
    print("TEST 2: Basic Navigation")
    print("=" * 80)
    
    try:
        from web_execution import WebExecutionPipeline, WebExecutionConfig
        
        config = WebExecutionConfig(headless=False, timeout_seconds=15)
        pipeline = WebExecutionPipeline(config)
        await pipeline.initialize()
        
        # Test task
        task = {
            'task_id': 'nav_test',
            'ai_prompt': 'Navigate to Google',
            'web_params': {
                'url': 'https://www.google.com',
                'action': 'navigate',
                'wait_for': 'networkidle'
            }
        }
        
        result = await pipeline.execute_web_task(task, session_id='test')
        
        await pipeline.cleanup()
        
        if result.validation_passed:
            print(f"✅ Navigation successful")
            print(f"   Final URL: {result.page_url}")
            return True
        else:
            print(f"❌ Navigation failed")
            print(f"   Errors: {result.validation_errors}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

# ============================================================================
# TEST 3: Form Interaction
# ============================================================================

async def test_form_interaction():
    """Test filling forms and clicking buttons"""
    print("\n" + "=" * 80)
    print("TEST 3: Form Interaction (Google Search)")
    print("=" * 80)
    
    try:
        from web_execution import WebExecutionPipeline, WebExecutionConfig
        
        config = WebExecutionConfig(headless=False, timeout_seconds=20)
        pipeline = WebExecutionPipeline(config)
        await pipeline.initialize()
        
        # Task 1: Navigate
        nav_task = {
            'task_id': 'form_nav',
            'ai_prompt': 'Navigate to Google',
            'web_params': {
                'url': 'https://www.google.com',
                'action': 'navigate'
            }
        }
        
        result1 = await pipeline.execute_web_task(nav_task, session_id='test')
        
        if not result1.validation_passed:
            print("❌ Navigation failed")
            await pipeline.cleanup()
            return False
        
        print("✅ Step 1: Navigation successful")
        
        # Task 2: Search
        search_task = {
            'task_id': 'form_search',
            'ai_prompt': 'Search for Playwright Python',
            'web_params': {
                'selector': 'textarea[name="q"]',
                'action': 'fill',
                'text': 'Playwright Python'
            }
        }
        
        result2 = await pipeline.execute_web_task(search_task, session_id='test')
        
        await pipeline.cleanup()
        
        if result2.validation_passed:
            print("✅ Step 2: Form fill successful")
            return True
        else:
            print("❌ Form fill failed")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

# ============================================================================
# TEST 4: Data Extraction
# ============================================================================

async def test_data_extraction():
    """Test scraping data from webpage"""
    print("\n" + "=" * 80)
    print("TEST 4: Data Extraction")
    print("=" * 80)
    
    try:
        from web_execution import WebExecutionPipeline, WebExecutionConfig
        
        config = WebExecutionConfig(headless=False, timeout_seconds=20)
        pipeline = WebExecutionPipeline(config)
        await pipeline.initialize()
        
        # Navigate to a page with extractable content
        nav_task = {
            'task_id': 'extract_nav',
            'ai_prompt': 'Navigate to example.com',
            'web_params': {
                'url': 'https://example.com',
                'action': 'navigate'
            }
        }
        
        result1 = await pipeline.execute_web_task(nav_task, session_id='test')
        
        if not result1.validation_passed:
            print("❌ Navigation failed")
            await pipeline.cleanup()
            return False
        
        # Extract text
        extract_task = {
            'task_id': 'extract_text',
            'ai_prompt': 'Extract heading text',
            'web_params': {
                'selector': 'h1',
                'action': 'extract'
            }
        }
        
        result2 = await pipeline.execute_web_task(extract_task, session_id='test')
        
        await pipeline.cleanup()
        
        if result2.validation_passed and result2.extracted_data:
            print(f"✅ Data extraction successful")
            print(f"   Extracted: {result2.extracted_data}")
            return True
        else:
            print("❌ Data extraction failed")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

# ============================================================================
# TEST 5: RAG Integration (if embeddings available)
# ============================================================================

async def test_rag_integration():
    """Test RAG system generating Playwright code"""
    print("\n" + "=" * 80)
    print("TEST 5: RAG Integration")
    print("=" * 80)
    
    try:
        # Import from web directory's code_generation.py
        from code_generation import RAGSystem, RAGConfig
        
        from web_execution import WebExecutionPipeline, WebExecutionConfig
        
        # Initialize RAG to get correct paths
        print("🔧 Initializing RAG system...")
        rag_config = RAGConfig()  # Already defaults to playwright
        
        # Check if Playwright embeddings exist using RAG's configured path
        if not rag_config.vectordb_dir.exists():
            print(f"⏭️  Skipping: Playwright embeddings not found at {rag_config.vectordb_dir}")
            print(f"   Run embeddin_training.ipynb first with library_name='playwright'")
            return None
        
        rag = RAGSystem(rag_config)
        rag.initialize()
        
        # Generate code
        query = "Navigate to Google using Playwright"
        print(f"🔍 Query: {query}")
        
        result = rag.generate_code(query)
        
        if result.get('code'):
            print("✅ RAG code generation successful")
            print(f"   Generated {len(result['code'])} chars")
            print("\nGenerated Code Preview:")
            print("-" * 40)
            print(result['code'][:300] + "..." if len(result['code']) > 300 else result['code'])
            print("-" * 40)
            return True
        else:
            print("❌ RAG failed to generate code")
            return False
            
    except ImportError as e:
        print(f"⏭️  Skipping: RAG components not available ({e})")
        return None
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

# ============================================================================
# TEST 6: Unified Router
# ============================================================================

async def test_unified_router():
    """Test routing between desktop and web execution"""
    print("\n" + "=" * 80)
    print("TEST 6: Unified Router")
    print("=" * 80)
    
    try:
        from unified_execution_router import UnifiedExecutionRouter
        
        router = UnifiedExecutionRouter()
        
        # Test web routing
        web_task = {
            'task_id': 'router_web',
            'ai_prompt': 'Navigate to Google',
            'context': 'web',
            'web_params': {
                'url': 'https://www.google.com',
                'action': 'navigate'
            }
        }
        
        print("🧪 Testing web routing...")
        result = await router.execute_task(web_task, session_id='test')
        
        await router.cleanup()
        
        if result['status'] == 'success':
            print("✅ Router web execution successful")
            return True
        else:
            print(f"❌ Router failed: {result.get('error')}")
            return False
            
    except ImportError as e:
        print(f"⏭️  Skipping: Router not available ({e})")
        return None
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

# ============================================================================
# TEST 7: End-to-End Amazon Search (Real Workflow)
# ============================================================================

async def test_amazon_workflow():
    """Test real-world workflow: Search Amazon for products"""
    print("\n" + "=" * 80)
    print("TEST 7: End-to-End Amazon Workflow")
    print("=" * 80)
    print("This will search for 'white socks' on Amazon and extract results")
    print()
    
    response = input("Continue? (y/n): ").lower()
    if response != 'y':
        print("⏭️  Skipping")
        return None
    
    try:
        from web_execution import WebExecutionPipeline, WebExecutionConfig
        
        config = WebExecutionConfig(headless=False, timeout_seconds=30)
        pipeline = WebExecutionPipeline(config)
        await pipeline.initialize()
        
        session_id = 'amazon_test'
        
        # Step 1: Navigate to Amazon
        print("\n🔗 Step 1: Navigate to Amazon...")
        nav_task = {
            'task_id': 'amazon_nav',
            'ai_prompt': 'Navigate to Amazon',
            'web_params': {
                'url': 'https://www.amazon.com',
                'action': 'navigate',
                'wait_for': 'networkidle'
            }
        }
        
        result1 = await pipeline.execute_web_task(nav_task, session_id)
        
        if not result1.validation_passed:
            print("❌ Navigation failed")
            await pipeline.cleanup()
            return False
        
        print("✅ Navigation successful")
        
        # Step 2: Search for white socks
        print("\n🔍 Step 2: Search for 'white socks'...")
        search_task = {
            'task_id': 'amazon_search',
            'ai_prompt': 'Search for white socks',
            'web_params': {
                'selector': '#twotabsearchtextbox',
                'action': 'fill',
                'text': 'white socks'
            }
        }
        
        result2 = await pipeline.execute_web_task(search_task, session_id)
        
        if not result2.validation_passed:
            print("❌ Search input failed")
            await pipeline.cleanup()
            return False
        
        print("✅ Search input successful")
        
        # Step 3: Click search button
        print("\n🖱️  Step 3: Click search button...")
        click_task = {
            'task_id': 'amazon_click',
            'ai_prompt': 'Click search button',
            'web_params': {
                'selector': '#nav-search-submit-button',
                'action': 'click'
            }
        }
        
        result3 = await pipeline.execute_web_task(click_task, session_id)
        
        if not result3.validation_passed:
            print("❌ Click failed")
            await pipeline.cleanup()
            return False
        
        print("✅ Search submitted")
        
        # Step 4: Extract product titles
        print("\n📊 Step 4: Extract product information...")
        extract_task = {
            'task_id': 'amazon_extract',
            'ai_prompt': 'Extract product titles',
            'web_params': {
                'selector': '.s-result-item h2',
                'action': 'extract'
            }
        }
        
        result4 = await pipeline.execute_web_task(extract_task, session_id)
        
        await pipeline.cleanup()
        
        if result4.validation_passed and result4.extracted_data:
            print("✅ Data extraction successful")
            print(f"\nFound {len(result4.extracted_data)} products:")
            for i, product in enumerate(result4.extracted_data[:5], 1):
                print(f"  {i}. {product[:80]}...")
            return True
        else:
            print("❌ Data extraction failed")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

# ============================================================================
# RUN ALL TESTS
# ============================================================================

async def run_all_tests():
    """Run all test cases"""
    print("\n" + "=" * 80)
    print("WEB AUTOMATION TEST SUITE")
    print("=" * 80)
    print("This will test all web automation components")
    print()
    
    tests = [
        ("Browser Launch", test_browser_launch),
        ("Basic Navigation", test_basic_navigation),
        ("Form Interaction", test_form_interaction),
        ("Data Extraction", test_data_extraction),
        ("RAG Integration", test_rag_integration),
        ("Unified Router", test_unified_router),
        ("Amazon Workflow", test_amazon_workflow),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results[test_name] = result
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results[test_name] = False
    
    # Print summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for r in results.values() if r is True)
    failed = sum(1 for r in results.values() if r is False)
    skipped = sum(1 for r in results.values() if r is None)
    
    for test_name, result in results.items():
        if result is True:
            status = "✅ PASSED"
        elif result is False:
            status = "❌ FAILED"
        else:
            status = "⏭️  SKIPPED"
        
        print(f"{status:15} {test_name}")
    
    print()
    print(f"Total: {len(results)} tests")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Skipped: {skipped}")
    
    if failed == 0:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️  {failed} test(s) failed")
    
    print()

def main():
    """Main test entry point"""
    import sys
    
    if len(sys.argv) > 1:
        test_name = sys.argv[1].lower()
        
        test_map = {
            'browser': test_browser_launch,
            'nav': test_basic_navigation,
            'form': test_form_interaction,
            'extract': test_data_extraction,
            'rag': test_rag_integration,
            'router': test_unified_router,
            'amazon': test_amazon_workflow,
        }
        
        if test_name in test_map:
            print(f"Running single test: {test_name}")
            asyncio.run(test_map[test_name]())
        else:
            print(f"Unknown test: {test_name}")
            print(f"Available tests: {', '.join(test_map.keys())}")
    else:
        asyncio.run(run_all_tests())

if __name__ == "__main__":
    main()