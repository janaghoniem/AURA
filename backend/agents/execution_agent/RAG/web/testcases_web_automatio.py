# ============================================================================
# WEB AUTOMATION TEST CASES - COMPREHENSIVE
# ============================================================================
# Test 1: Full YouTube workflow (navigate, search, play, pause, skip, mute)
# Test 2: Navigate to site and save content locally

import asyncio
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# TEST 1: FULL YOUTUBE WORKFLOW
# ============================================================================

async def test_youtube_full_workflow():
    """
    Test complete YouTube automation workflow:
    1. Navigate to YouTube
    2. Search for a video
    3. Play the video
    4. Pause the video
    5. Skip to next video
    6. Mute the video
    """
    
    logger.info("="*80)
    logger.info("TEST 1: FULL YOUTUBE WORKFLOW")
    logger.info("="*80)
    
    # Import web execution system
    from web_execution import WebExecutionPipeline, WebExecutionConfig
    
    # Initialize pipeline
    config = WebExecutionConfig(
        headless=False,  # Show browser to see actions
        timeout_seconds=60,
        screenshots_enabled=True,
        screenshot_dir="test_screenshots_youtube",
        enable_verification=True,
        enable_page_context=True
    )
    
    pipeline = WebExecutionPipeline(config)
    await pipeline.initialize()
    
    session_id = "youtube_test_session"
    
    # Define test tasks
    tasks = [
        # Task 1: Navigate to YouTube
        {
            "task_id": "youtube_nav",
            "ai_prompt": "Navigate to YouTube homepage",
            "web_params": {"action": "navigate"}
        },
        
        # Task 2: Search for "Python tutorial"
        {
            "task_id": "youtube_search",
            "ai_prompt": "Search for 'Python tutorial' on YouTube",
            "web_params": {"action": "fill", "text": "Python tutorial"}
        },
        
        # Task 3: Click on first video result
        {
            "task_id": "youtube_play",
            "ai_prompt": "Click on the first video result to play it",
            "web_params": {"action": "click"}
        },
        
        # Wait a bit for video to start
        {
            "task_id": "youtube_wait",
            "ai_prompt": "Wait 3 seconds for video to load",
            "web_params": {"action": "wait"}
        },
        
        # Task 4: Pause the video
        {
            "task_id": "youtube_pause",
            "ai_prompt": "Pause the video",
            "web_params": {"action": "media_control"}
        },
        
        # Wait a bit
        {
            "task_id": "youtube_wait2",
            "ai_prompt": "Wait 2 seconds",
            "web_params": {"action": "wait"}
        },
        
        # Task 5: Resume playing
        {
            "task_id": "youtube_play2",
            "ai_prompt": "Play the video",
            "web_params": {"action": "media_control"}
        },
        
        # Wait a bit
        {
            "task_id": "youtube_wait3",
            "ai_prompt": "Wait 3 seconds",
            "web_params": {"action": "wait"}
        },
        
        # Task 6: Skip to next video
        {
            "task_id": "youtube_next",
            "ai_prompt": "Skip to the next video",
            "web_params": {"action": "media_control"}
        },
        
        # Wait for next video to load
        {
            "task_id": "youtube_wait4",
            "ai_prompt": "Wait 3 seconds for next video",
            "web_params": {"action": "wait"}
        },
        
        # Task 7: Mute the video
        {
            "task_id": "youtube_mute",
            "ai_prompt": "Mute the video sound",
            "web_params": {"action": "media_control"}
        },
    ]
    
    # Execute all tasks
    results = []
    
    for i, task in enumerate(tasks):
        logger.info(f"\n{'='*60}")
        logger.info(f"TASK {i+1}/{len(tasks)}: {task['ai_prompt']}")
        logger.info(f"{'='*60}")
        
        # Special handling for wait tasks
        if 'wait' in task['task_id']:
            wait_seconds = 2
            if '3 seconds' in task['ai_prompt']:
                wait_seconds = 3
            
            logger.info(f"⏳ Waiting {wait_seconds} seconds...")
            await asyncio.sleep(wait_seconds)
            
            results.append({
                'task_id': task['task_id'],
                'status': 'success',
                'output': f'Waited {wait_seconds} seconds'
            })
            continue
        
        # Execute task
        result = await pipeline.execute_web_task(task, session_id)
        
        results.append({
            'task_id': task['task_id'],
            'status': 'success' if result.validation_passed else 'failed',
            'output': result.output,
            'error': result.error,
            'screenshot': result.screenshot_path
        })
        
        # Check if task succeeded
        if result.validation_passed:
            logger.info(f"✅ Task succeeded: {task['task_id']}")
        else:
            logger.error(f"❌ Task failed: {task['task_id']}")
            logger.error(f"   Error: {result.error}")
            break  # Stop on first failure
        
        # Small delay between tasks
        await asyncio.sleep(1)
    
    # Print summary
    logger.info("\n" + "="*80)
    logger.info("TEST 1 SUMMARY - YOUTUBE WORKFLOW")
    logger.info("="*80)
    
    success_count = sum(1 for r in results if r['status'] == 'success')
    total_count = len(results)
    
    logger.info(f"Total tasks: {total_count}")
    logger.info(f"Successful: {success_count}")
    logger.info(f"Failed: {total_count - success_count}")
    logger.info(f"Success rate: {success_count/total_count*100:.1f}%")
    
    logger.info("\nTask Results:")
    for r in results:
        status_icon = "✅" if r['status'] == 'success' else "❌"
        logger.info(f"  {status_icon} {r['task_id']}: {r['status']}")
        if r.get('screenshot'):
            logger.info(f"     Screenshot: {r['screenshot']}")
    
    # Cleanup
    await pipeline.cleanup()
    
    return results

# ============================================================================
# TEST 2: NAVIGATE TO SITE AND SAVE CONTENT LOCALLY
# ============================================================================

async def test_save_content_locally():
    """
    Test navigating to a site and saving content locally:
    1. Navigate to example.com
    2. Extract page title and text content
    3. Save to local file
    """
    
    logger.info("\n" + "="*80)
    logger.info("TEST 2: SAVE CONTENT LOCALLY")
    logger.info("="*80)
    
    # Import web execution system
    from web_execution import WebExecutionPipeline, WebExecutionConfig
    
    # Initialize pipeline
    config = WebExecutionConfig(
        headless=False,
        timeout_seconds=30,
        screenshots_enabled=True,
        screenshot_dir="test_screenshots_save",
        enable_verification=True,
        enable_page_context=True
    )
    
    pipeline = WebExecutionPipeline(config)
    await pipeline.initialize()
    
    session_id = "save_test_session"
    
    # Define test tasks
    tasks = [
        # Task 1: Navigate to Wikipedia Python page
        {
            "task_id": "nav_wiki",
            "ai_prompt": "Navigate to Wikipedia Python programming language page",
            "web_params": {"action": "navigate"}
        },
        
        # Task 2: Extract page content
        {
            "task_id": "extract_content",
            "ai_prompt": "Extract the page title and first paragraph from the Wikipedia article",
            "web_params": {"action": "extract"}
        },
    ]
    
    # Execute tasks
    results = []
    extracted_data = {}
    
    for i, task in enumerate(tasks):
        logger.info(f"\n{'='*60}")
        logger.info(f"TASK {i+1}/{len(tasks)}: {task['ai_prompt']}")
        logger.info(f"{'='*60}")
        
        result = await pipeline.execute_web_task(task, session_id)
        
        results.append({
            'task_id': task['task_id'],
            'status': 'success' if result.validation_passed else 'failed',
            'output': result.output,
            'error': result.error,
            'extracted_data': result.extracted_data,
            'screenshot': result.screenshot_path
        })
        
        if result.validation_passed:
            logger.info(f"✅ Task succeeded: {task['task_id']}")
            
            # Store extracted data
            if result.extracted_data:
                extracted_data.update(result.extracted_data)
        else:
            logger.error(f"❌ Task failed: {task['task_id']}")
            logger.error(f"   Error: {result.error}")
            break
        
        await asyncio.sleep(1)
    
    # Task 3: Save content to local file
    logger.info("\n" + "="*60)
    logger.info("TASK 3: SAVING CONTENT TO LOCAL FILE")
    logger.info("="*60)
    
    output_dir = Path("test_output_files")
    output_dir.mkdir(exist_ok=True)
    
    output_file = output_dir / "wikipedia_python_content.txt"
    
    try:
        # Get page for final content extraction
        page = pipeline.sessions.get(session_id)
        
        if page:
            # Extract content using JavaScript
            content = await page.evaluate("""
                () => {
                    const title = document.title;
                    const firstParagraph = document.querySelector('p')?.textContent || '';
                    const allParagraphs = Array.from(document.querySelectorAll('p'))
                        .slice(0, 5)
                        .map(p => p.textContent)
                        .join('\\n\\n');
                    
                    return {
                        title: title,
                        firstParagraph: firstParagraph,
                        content: allParagraphs,
                        url: window.location.href,
                        timestamp: new Date().toISOString()
                    };
                }
            """)
            
            # Write to file
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"SAVED CONTENT FROM: {content['url']}\n")
                f.write(f"TIMESTAMP: {content['timestamp']}\n")
                f.write(f"{'='*80}\n\n")
                f.write(f"TITLE: {content['title']}\n\n")
                f.write(f"{'='*80}\n")
                f.write(f"CONTENT:\n\n")
                f.write(content['content'])
            
            logger.info(f"✅ Content saved to: {output_file}")
            logger.info(f"   File size: {output_file.stat().st_size} bytes")
            
            results.append({
                'task_id': 'save_local',
                'status': 'success',
                'output': f'Saved to {output_file}',
                'file_path': str(output_file)
            })
            
        else:
            logger.error("❌ No page session available")
            results.append({
                'task_id': 'save_local',
                'status': 'failed',
                'error': 'No page session'
            })
    
    except Exception as e:
        logger.error(f"❌ Failed to save content: {e}")
        results.append({
            'task_id': 'save_local',
            'status': 'failed',
            'error': str(e)
        })
    
    # Print summary
    logger.info("\n" + "="*80)
    logger.info("TEST 2 SUMMARY - SAVE CONTENT LOCALLY")
    logger.info("="*80)
    
    success_count = sum(1 for r in results if r['status'] == 'success')
    total_count = len(results)
    
    logger.info(f"Total tasks: {total_count}")
    logger.info(f"Successful: {success_count}")
    logger.info(f"Failed: {total_count - success_count}")
    logger.info(f"Success rate: {success_count/total_count*100:.1f}%")
    
    logger.info("\nTask Results:")
    for r in results:
        status_icon = "✅" if r['status'] == 'success' else "❌"
        logger.info(f"  {status_icon} {r['task_id']}: {r['status']}")
        if r.get('file_path'):
            logger.info(f"     Saved to: {r['file_path']}")
        if r.get('screenshot'):
            logger.info(f"     Screenshot: {r['screenshot']}")
    
    # Cleanup
    await pipeline.cleanup()
    
    return results

# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

async def run_all_tests():
    """Run all test cases"""
    
    logger.info("="*80)
    logger.info("WEB AUTOMATION COMPREHENSIVE TEST SUITE")
    logger.info("="*80)
    
    # Run Test 1: YouTube workflow
    test1_results = await test_youtube_full_workflow()
    
    # Wait between tests
    await asyncio.sleep(3)
    
    # Run Test 2: Save content locally
    test2_results = await test_save_content_locally()
    
    # Overall summary
    logger.info("\n" + "="*80)
    logger.info("OVERALL TEST SUMMARY")
    logger.info("="*80)
    
    test1_success = sum(1 for r in test1_results if r['status'] == 'success')
    test2_success = sum(1 for r in test2_results if r['status'] == 'success')
    
    logger.info(f"\nTest 1 (YouTube Workflow):")
    logger.info(f"  Success: {test1_success}/{len(test1_results)}")
    
    logger.info(f"\nTest 2 (Save Content Locally):")
    logger.info(f"  Success: {test2_success}/{len(test2_results)}")
    
    total_success = test1_success + test2_success
    total_tasks = len(test1_results) + len(test2_results)
    
    logger.info(f"\nOverall:")
    logger.info(f"  Total tasks: {total_tasks}")
    logger.info(f"  Successful: {total_success}")
    logger.info(f"  Failed: {total_tasks - total_success}")
    logger.info(f"  Success rate: {total_success/total_tasks*100:.1f}%")
    
    logger.info("\n" + "="*80)
    logger.info("ALL TESTS COMPLETED")
    logger.info("="*80)

# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    # Run all tests
    asyncio.run(run_all_tests())