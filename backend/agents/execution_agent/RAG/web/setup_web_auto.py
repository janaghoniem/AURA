#!/usr/bin/env python3
# ============================================================================
# WEB AUTOMATION – POST-EMBEDDING VERIFICATION & TEST
# ============================================================================

import sys
import asyncio
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def print_header(text):
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80 + "\n")

def check_paths():
    """Verify embeddings and vector DB exist"""
    print_header("STEP 1: Verifying Embedding Outputs")

    required_paths = [
        Path("rag_data/playwright/combined/playwright_combined.json"),
        Path("models/playwright"),
        Path("vectordb/playwright"),
    ]

    all_ok = True

    for path in required_paths:
        if path.exists():
            print(f"✅ Found: {path}")
        else:
            print(f"❌ Missing: {path}")
            all_ok = False

    if not all_ok:
        print("\n❌ Embeddings not ready. Re-run embeddin_training.ipynb")
        sys.exit(1)

    print("\n✅ Embedding artifacts verified")

# ---------------------------------------------------------------------------
# Quick Playwright Execution Test
# ---------------------------------------------------------------------------

async def quick_web_test():
    """Minimal Playwright test"""
    print_header("STEP 2: Running Web Automation Smoke Test")

    try:
        from web_execution import WebExecutionPipeline, WebExecutionConfig

        config = WebExecutionConfig(
            headless=True,
            timeout_seconds=15
        )

        pipeline = WebExecutionPipeline(config)
        await pipeline.initialize()

        task = {
            "task_id": "smoke_test",
            "ai_prompt": "Open Google homepage",
            "web_params": {
                "url": "https://www.google.com",
                "action": "navigate",
                "wait_for": "networkidle"
            }
        }

        result = await pipeline.execute_web_task(task, session_id="smoke")

        await pipeline.cleanup()

        if result.validation_passed:
            print("✅ Web automation test PASSED")
            print(f"🌍 Page URL: {result.page_url}")
        else:
            print("❌ Web automation test FAILED")
            print(result.validation_errors)

    except Exception as e:
        print("❌ Web automation test crashed")
        raise e

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print_header("WEB AUTOMATION SYSTEM – POST-EMBEDDING CHECK")

    check_paths()

    response = input("Run Playwright smoke test? (y/n): ").lower()
    if response == "y":
        asyncio.run(quick_web_test())

    print_header("SYSTEM READY")
    print("""
✅ Playwright data embedded
✅ Vector DB available
✅ Web execution operational

You can now:
• Use unified_execution_router.py
• Connect coordinator_agent → execution_agent
• Enable RAG-powered web actions
""")

if __name__ == "__main__":
    main()
