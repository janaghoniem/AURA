"""
Standalone test script for Coordinator Agent LLM output.
Tests task decomposition without needing the full agent infrastructure.
"""

import asyncio
import json
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

# Initialize LLM
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.2,
    max_output_tokens=2048
)

async def test_coordinator_llm(test_task: dict, test_name: str = "Test"):
    """
    Test the coordinator's LLM decomposition logic in isolation.
    
    Args:
        test_task: Input JSON from Language Agent
        test_name: Descriptive name for the test
    """
    print(f"\n{'='*80}")
    print(f"🧪 TEST: {test_name}")
    print(f"{'='*80}")
    print(f"\n📥 INPUT (from Language Agent):")
    print(json.dumps(test_task, indent=2))
    
    # Build the prompt (same as in coordinator_agent.py)
    prompt = f"""You are the YUSR Coordinator Agent. Decompose user tasks into executable subtasks.

# INPUT FROM LANGUAGE AGENT
{json.dumps(test_task, indent=2)}

# YOUR TASK
Analyze the input and determine if decomposition is needed:

**SIMPLE TASK** (single action):
- "open calculator" → Already complete, just add task_id
- "send discord message" → Already structured correctly

**COMPLEX TASK** (multiple steps with dependencies):
- "check moodle assignment and create word doc with analysis"
  → Step 1: Login to Moodle (web)
  → Step 2: Extract assignment text (web) 
  → Step 3: Analyze requirements (reasoning)
  → Step 4: Generate execution plan (reasoning)
  → Step 5: Create Word doc with content (local)

# EXECUTION CONTEXTS
- **local**: Desktop apps (PowerPoint, Word, Calculator, Discord desktop)
- **web**: Browser automation (Moodle login, form filling, data extraction)
- **system**: OS commands (file operations, scripts)
- **reasoning**: Text analysis, summarization, content generation, decision-making

# DEPENDENCY RULES
- **parallel**: Independent tasks (can run simultaneously)
- **sequential**: Dependent tasks (output of task N feeds task N+1)
- Use "depends_on" field to reference previous task_id

# OUTPUT FORMAT
Return ONLY valid JSON (no markdown, no explanations):

**For simple tasks** (no decomposition needed):
{{
  "needs_decomposition": false,
  "enhanced_task": {{
    "task_id": "uuid",
    "action": "same as input",
    "context": "local|web|system|reasoning",
    "params": {{ /* same as input, ensure action_type exists */ }},
    "priority": "normal",
    "timeout": 30,
    "retry_count": 3
  }}
}}

**For complex tasks** (decomposition required):
{{
  "needs_decomposition": true,
  "parallel": [
    {{
      "task_id": "uuid-1",
      "action": "descriptive_name",
      "context": "web",
      "params": {{
        "action_type": "login",
        "url": "https://moodle.edu",
        "username": "$USER",
        "password": "$PASS"
      }},
      "priority": "high",
      "timeout": 60
    }}
  ],
  "sequential": [
    {{
      "task_id": "uuid-2",
      "action": "extract_assignment",
      "context": "web",
      "params": {{
        "action_type": "extract_data",
        "selectors": {{
          "title": ".assignment-title",
          "description": ".assignment-body"
        }}
      }},
      "depends_on": "uuid-1"
    }},
    {{
      "task_id": "uuid-3",
      "action": "analyze_requirements",
      "context": "reasoning",
      "params": {{
        "prompt": "Analyze this assignment and create execution plan",
        "input_from": "uuid-2"
      }},
      "depends_on": "uuid-2"
    }}
  ]
}}

**If missing critical info** (ambiguous recipient, unclear platform):
{{
  "needs_clarification": true,
  "question": "Which Moodle course should I check? Please specify the course name."
}}

# CRITICAL RULES
1. Every task MUST have unique task_id (use uuid format like "uuid-1", "uuid-2")
2. Execution tasks MUST include "action_type" in params
3. Never invent information (if username unknown, use placeholder "$USER")
4. Preserve original intent from Language Agent input
5. For file operations, ensure paths are specific (not "desktop" but "C:\\Users\\$USER\\Desktop")

Now analyze the input task and return ONLY the JSON response:"""

    try:
        # Get LLM response
        print(f"\n⏳ Calling Gemini 2.5 Flash...")
        response = await llm.ainvoke(prompt)
        response_text = response.content if hasattr(response, 'content') else str(response)
        
        # Clean up markdown formatting
        response_text = response_text.strip()
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        
        response_text = response_text.strip()
        
        # Parse JSON
        plan = json.loads(response_text)
        
        # Pretty print output
        print(f"\n📤 COORDINATOR OUTPUT:")
        print(json.dumps(plan, indent=2))
        
        # Analysis
        print(f"\n🔍 ANALYSIS:")
        if plan.get("needs_clarification"):
            print(f"❓ Status: NEEDS CLARIFICATION")
            print(f"   Question: {plan['question']}")
        elif not plan.get("needs_decomposition"):
            print(f"✅ Status: SIMPLE TASK (no decomposition)")
            print(f"   Action: {plan['enhanced_task']['action']}")
            print(f"   Context: {plan['enhanced_task']['context']}")
        else:
            print(f"🔀 Status: COMPLEX TASK (decomposed)")
            parallel_count = len(plan.get("parallel", []))
            sequential_count = len(plan.get("sequential", []))
            print(f"   Parallel tasks: {parallel_count}")
            print(f"   Sequential tasks: {sequential_count}")
            
            if sequential_count > 0:
                print(f"\n   📋 Execution Flow:")
                for i, task in enumerate(plan["sequential"], 1):
                    depends = f" (depends on: {task.get('depends_on')})" if task.get('depends_on') else ""
                    print(f"      {i}. [{task['context']}] {task['action']}{depends}")
        
        print(f"\n✅ Test completed successfully!\n")
        return plan
        
    except json.JSONDecodeError as e:
        print(f"\n❌ JSON PARSING ERROR:")
        print(f"   {str(e)}")
        print(f"\n   Raw LLM Response:")
        print(f"   {response_text}")
        return None
    
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        return None


async def run_all_tests():
    """Run comprehensive test suite"""
    
    # TEST 1: Simple task (from your example)
    # await test_coordinator_llm(
    #     test_task={
    #         "action": "send_message",
    #         "context": "local",
    #         "params": {
    #             "action_type": "send_message",
    #             "platform": "discord",
    #             "recipient": "upload the recently downloaded pdf to the grad"
    #         },
    #         "task_id": "",
    #         "depends_on": "",
    #         "priority": "",
    #         "timeout": "",
    #         "retry_count": ""
    #     },
    #     test_name="Simple Discord Message"
    # )
    
    # # TEST 2: Complex multi-step task
    # await test_coordinator_llm(
    #     test_task={
    #         "action": "check_moodle_assignment_and_create_report",
    #         "context": "web",
    #         "params": {
    #             "course": "AI Ethics",
    #             "assignment_type": "presentation",
    #             "output_format": "word_document"
    #         },
    #         "task_id": "",
    #         "priority": "high"
    #     },
    #     test_name="Complex Moodle + Word Task"
    # )
    
    # # TEST 3: Ambiguous task (should trigger clarification)
    # await test_coordinator_llm(
    #     test_task={
    #         "action": "send_message",
    #         "context": "local",
    #         "params": {
    #             "action_type": "send_message",
    #             "message": "Hello team!"
    #         },
    #         "task_id": ""
    #     },
    #     test_name="Ambiguous Message (Missing Platform)"
    # )
    
    # # TEST 4: Another simple task
    # await test_coordinator_llm(
    #     test_task={
    #         "action": "open_calculator",
    #         "context": "local",
    #         "params": {
    #             "action_type": "open_app",
    #             "app_name": "Calculator"
    #         },
    #         "task_id": ""
    #     },
    #     test_name="Simple App Launch"
    # )
    
    # # TEST 5: Web automation task
    # await test_coordinator_llm(
    #     test_task={
    #         "action": "login_and_download_grades",
    #         "context": "web",
    #         "params": {
    #             "url": "https://student.portal.edu",
    #             "username": "student123",
    #             "download_item": "transcript"
    #         },
    #         "task_id": ""
    #     },
    #     test_name="Web Login + Download"
    # )
    
    # # TEST 6: Your real-world complex example
    # await test_coordinator_llm(
    #     test_task={
    #         "action": "analyze_presentation_assignment_from_moodle",
    #         "context": "web",
    #         "params": {
    #             "platform": "moodle",
    #             "course": "Advanced Machine Learning",
    #             "task_type": "presentation",
    #             "output": "word_document_on_desktop",
    #             "include": "full_execution_plan"
    #         },
    #         "task_id": "",
    #         "priority": "urgent"
    #     },
    #     test_name="Full Moodle → Analysis → Word Pipeline"
    # )


if __name__ == "__main__":
    print("""
╔═══════════════════════════════════════════════════════════════════════════╗
║                   YUSR COORDINATOR AGENT - LLM TESTER                      ║
║                                                                            ║
║  This script tests the Coordinator's task decomposition logic             ║
║  without needing the full agent infrastructure.                           ║
║                                                                            ║
║  Tests: Simple tasks, complex workflows, clarification handling           ║
╚═══════════════════════════════════════════════════════════════════════════╝
    """)
    
    asyncio.run(run_all_tests())
    
    print(f"\n{'='*80}")
    print("🎉 All tests completed!")
    print(f"{'='*80}\n")