"""
Demo Coordinator Interface
Simulates Coordinator Agent delegating complex multi-step tasks to Execution Agent

This demonstrates a realistic scenario:
1. Search web for topic
2. Extract information
3. Create PowerPoint presentation
4. Save to specific folder

Author: Accessibility AI Team
Version: 1.0.0
"""

import json
import time
import os
from datetime import datetime
from typing import List, Dict

from exec_agent_main import ExecutionAgent
from exec_agent_models import ExecutionTask, ExecutionResult
from exec_agent_config import ExecutionContext, ActionStatus


class CoordinatorInterface:
    """
    Simulates Coordinator Agent sending sequential tasks
    Each task depends on the previous task's success
    """
    
    def __init__(self):
        self.execution_agent = ExecutionAgent()
        self.task_history = []
        self.current_workflow = None
    
    def print_header(self):
        """Print demo header"""
        print("\n" + "="*70)
        print("COORDINATOR AGENT → EXECUTION AGENT DEMO")
        print("Complex Multi-Step Workflow Simulation")
        print("="*70)
        print("\nScenario: Web Research → PowerPoint Presentation")
        print("="*70 + "\n")
    
    def print_workflow_plan(self, workflow: Dict):
        """Display the planned workflow"""
        print("\nWORKFLOW PLAN:")
        print("-" * 70)
        print(f"Workflow ID: {workflow['workflow_id']}")
        print(f"Topic: {workflow['topic']}")
        print(f"Total Steps: {len(workflow['steps'])}\n")
        
        for i, step in enumerate(workflow['steps'], 1):
            print(f"{i}. {step['name']}")
            print(f"   Context: {step['context']}")
            print(f"   Description: {step['description']}")
            if step.get('depends_on'):
                print(f"   Depends on: Step {step['depends_on']}")
            print()
        
        print("-" * 70)
    
    def create_workflow(self, topic: str = None) -> Dict:
        """
        Create a multi-step workflow
        
        Args:
            topic: Research topic (if None, will prompt user)
        
        Returns:
            Workflow dictionary
        """
        if not topic:
            print("\nWhat would you like to research and present?")
            print("Examples:")
            print("  - Artificial Intelligence in Healthcare")
            print("  - Renewable Energy Technologies")
            print("  - Egyptian Ancient Architecture")
            print("  - Machine Learning Algorithms\n")
            topic = input("Enter your topic: ").strip()
            
            if not topic:
                topic = "Artificial Intelligence"
                print(f"Using default topic: {topic}")
        
        workflow_id = f"workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        workflow = {
            "workflow_id": workflow_id,
            "topic": topic,
            "start_time": datetime.now().isoformat(),
            "status": "planned",
            "steps": [
                {
                    "step_id": 1,
                    "name": "Open Web Browser",
                    "context": "local",
                    "description": "Launch default web browser",
                    "action_type": "open_app",
                    "params": {
                        "app_name": "Edge"  # or "msedge" or "firefox"
                    },
                    "depends_on": None
                },
                {
                    "step_id": 2,
                    "name": "Search for Topic",
                    "context": "local",
                    "description": f"Navigate to search engine and search for '{topic}'",
                    "action_type": "web_search",
                    "params": {
                        "search_query": topic,
                        "search_engine": "google"
                    },
                    "depends_on": 1
                },
                {
                    "step_id": 2.5,
                    "name": "Extract Web Content",
                    "context": "local",
                    "description": "Extract main text from the first search result website.",
                    "action_type": "extract_web_content",
                    "params": {
                        "search_query": topic,
                        "search_engine": "google"
                    },
                    "depends_on": 2
                },
                {
                    "step_id": 3,
                    "name": "Create Presentation Folder",
                    "context": "system",
                    "description": "Create folder 'agent_presentation' on Desktop",
                    "action_type": "create_folder",
                    "params": {
                        "folder_path": os.path.join(
                            os.path.expanduser("~"),
                            "Desktop",
                            "agent_presentation"
                        )
                    },
                    "depends_on": None  # Can run independently
                },
                {
                    "step_id": 4,
                    "name": "Open PowerPoint",
                    "context": "local",
                    "description": "Launch Microsoft PowerPoint application",
                    "action_type": "open_app",
                    "params": {
                        "app_name": "PowerPoint"
                    },
                    "depends_on": 3
                },
                {
                    "step_id": 4.5,
                    "name": "New Blank Presentation",
                    "context": "local",
                    "description": "Ensure a new blank PowerPoint presentation is started.",
                    "action_type": "create_new_presentation",
                    "params": {},
                    "depends_on": 4
                },
                {
                    "step_id": 5,
                    "name": "Create Title Slide",
                    "context": "local",
                    "description": "Add title and subtitle to first slide",
                    "action_type": "create_title_slide",
                    "params": {
                        "title": topic,
                        "subtitle": f"Research Presentation - {datetime.now().strftime('%B %Y')}"
                    },
                    "depends_on": 4.5
                },
                {
                    "step_id": 6,
                    "name": "Add Content Slides",
                    "context": "local",
                    "description": "Add main content slides using extracted text.",
                    "action_type": "add_content_slides",
                    "params": {
                        "slides": [
                            {"title": "Web Content Summary", "content": "{{web_content}}"}
                        ]
                    },
                    "depends_on": 5
                },
                {
                    "step_id": 6.5,
                    "name": "Create Extra Slide",
                    "context": "local",
                    "description": "Demonstrate single-slide addition.",
                    "action_type": "create_new_slide",
                    "params": {
                        "title": "Custom Slide",
                        "content": "This is an example of creating a single new slide via atomic task."
                    },
                    "depends_on": 6
                },
                {
                    "step_id": 7,
                    "name": "Save Presentation",
                    "context": "local",
                    "description": "Save PowerPoint file to agent_presentation folder",
                    "action_type": "save_presentation",
                    "params": {
                        "filename": f"{topic.replace(' ', '_')}_presentation.pptx",
                        "folder": os.path.join(
                            os.path.expanduser("~"),
                            "Desktop",
                            "agent_presentation"
                        )
                    },
                    "depends_on": 6
                },
                {
                    "step_id": 8,
                    "name": "Close PowerPoint",
                    "context": "local",
                    "description": "Close PowerPoint application",
                    "action_type": "close_app",
                    "params": {
                        "app_name": "PowerPoint"
                    },
                    "depends_on": 7
                },
                {
                    "step_id": 9,
                    "name": "Verify Files",
                    "context": "system",
                    "description": "Verify presentation file was saved successfully",
                    "action_type": "verify_file",
                    "params": {
                        "folder": os.path.join(
                            os.path.expanduser("~"),
                            "Desktop",
                            "agent_presentation"
                        )
                    },
                    "depends_on": 8
                }
            ]
        }
        
        return workflow
    
    def execute_step(self, step: Dict, workflow_context: Dict) -> ExecutionResult:
        """
        Execute a single workflow step with comprehensive error handling
        
        Args:
            step: Step dictionary
            workflow_context: Shared context between steps
        
        Returns:
            ExecutionResult
        """
        try:
            print(f"\n{'='*70}")
            print(f"STEP {step['step_id']}: {step['name']}")
            print(f"{'='*70}")
            print(f"Description: {step['description']}")
            print(f"Context: {step['context']}")
            print(f"Action: {step['action_type']}")
            
            if step.get('depends_on'):
                print(f"Dependency: Requires Step {step['depends_on']} to succeed")
            
            print(f"\nCoordinator → Execution Agent: Delegating task...")
            print("-" * 70)
            
            # Validate step structure
            if not step.get('action_type'):
                error_msg = f"Missing action_type in step {step.get('step_id', 'unknown')}"
                print(f"ERROR: {error_msg}")
                return ExecutionResult(
                    status=ActionStatus.FAILED.value,
                    task_id=f"{workflow_context.get('workflow_id', 'unknown')}_step_{step.get('step_id', 'unknown')}",
                    context=step.get('context', 'unknown'),
                    action=step.get('action_type', 'unknown'),
                    details=error_msg,
                    logs=[error_msg],
                    timestamp=datetime.now().isoformat(),
                    duration=0.0,
                    error=error_msg
                )
            
            # Create ExecutionTask
            try:
                task = ExecutionTask(
                    action_type=step['action_type'],
                    context=step.get('context', 'local'),
                    strategy=self._get_strategy(step.get('context', 'local')),
                    params={
                        "action_type": step['action_type'],
                        **step.get('params', {})
                    },
                    task_id=f"{workflow_context.get('workflow_id', 'unknown')}_step_{step.get('step_id', 'unknown')}",
                    priority="normal",
                    retry_count=2
                )
            except Exception as e:
                error_msg = f"Failed to create ExecutionTask: {str(e)}"
                print(f"ERROR: {error_msg}")
                return ExecutionResult(
                    status=ActionStatus.FAILED.value,
                    task_id=f"{workflow_context.get('workflow_id', 'unknown')}_step_{step.get('step_id', 'unknown')}",
                    context=step.get('context', 'unknown'),
                    action=step.get('action_type', 'unknown'),
                    details=error_msg,
                    logs=[error_msg],
                    timestamp=datetime.now().isoformat(),
                    duration=0.0,
                    error=error_msg
                )
            
            # Execute via Execution Agent with error handling
            start_time = time.time()
            try:
                result = self.execution_agent.execute(task)
                duration = time.time() - start_time
            except Exception as e:
                error_msg = f"Agent execution exception: {str(e)}"
                print(f"ERROR: {error_msg}")
                import traceback
                traceback.print_exc()
                result = ExecutionResult(
                    status=ActionStatus.FAILED.value,
                    task_id=task.task_id,
                    context=task.context,
                    action=task.action_type,
                    details=error_msg,
                    logs=[error_msg],
                    timestamp=datetime.now().isoformat(),
                    duration=time.time() - start_time,
                    error=error_msg
                )
            
            # Display result
            self._print_execution_result(result, step.get('step_id', 0))
            
            # Store in history
            try:
                self.task_history.append({
                    "step": step,
                    "result": result.to_dict() if hasattr(result, 'to_dict') else result,
                    "timestamp": datetime.now().isoformat()
                })
            except Exception as e:
                print(f"Warning: Failed to store step in history: {e}")
            
            return result
            
        except Exception as e:
            # Catch-all for any unexpected errors
            error_msg = f"Unexpected error in execute_step: {str(e)}"
            print(f"ERROR: {error_msg}")
            import traceback
            traceback.print_exc()
            return ExecutionResult(
                status=ActionStatus.FAILED.value,
                task_id=f"{workflow_context.get('workflow_id', 'unknown')}_step_{step.get('step_id', 'unknown')}",
                context=step.get('context', 'unknown'),
                action=step.get('action_type', 'unknown'),
                details=error_msg,
                logs=[error_msg],
                timestamp=datetime.now().isoformat(),
                duration=0.0,
                error=error_msg
            )
    
    def _get_strategy(self, context: str) -> str:
        """Get strategy based on context"""
        strategies = {
            "local": "local",
            "web": "selenium",
            "system": "subprocess"
        }
        return strategies.get(context, "default")
    
    def _print_execution_result(self, result: ExecutionResult, step_id: int):
        """Print formatted execution result"""
        print("\nEXECUTION RESULT:")
        print("-" * 70)
        
        # Status with color coding
        status_symbols = {
            "success": "[OK]",
            "failed": "[FAILED]",
            "partial": "[PARTIAL]",
            "awaiting_confirmation": "[AWAITING]"
        }
        symbol = status_symbols.get(result.status, "[?]")
        
        print(f"Status: {symbol} {result.status.upper()}")
        print(f"Duration: {result.duration:.2f}s")
        print(f"Details: {result.details}")
        
        if result.logs:
            print(f"\nExecution Logs:")
            for log in result.logs:
                print(f"   • {log}")
        
        if result.error:
            print(f"\nError: {result.error}")
        
        if result.screenshot_path:
            print(f"\nScreenshot: {result.screenshot_path}")
        
        print("-" * 70)
    
    def _replace_placeholders(self, obj, context):
        """
        Recursively replace {{key}} placeholders with context values in strings within obj
        Handles errors gracefully
        """
        try:
            if isinstance(obj, dict):
                return {k: self._replace_placeholders(v, context) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [self._replace_placeholders(item, context) for item in obj]
            elif isinstance(obj, str):
                result = obj
                for k, v in context.items():
                    placeholder = f"{{{{{k}}}}}"
                    if placeholder in result:
                        try:
                            result = result.replace(placeholder, str(v))
                        except Exception as e:
                            print(f"Warning: Failed to replace placeholder {placeholder}: {e}")
                return result
            return obj
        except Exception as e:
            print(f"Warning: Error in placeholder replacement: {e}")
            return obj  # Return original if replacement fails

    def execute_workflow(self, workflow: Dict, interactive: bool = True):
        self.current_workflow = workflow
        workflow['status'] = 'running'
        completed_steps = set()
        failed_steps = set()
        total_steps = len(workflow['steps'])
        step_outputs = {}  # Track outputs to fill placeholders

        for i, step in enumerate(workflow['steps'], 1):
            if step.get('depends_on') and step['depends_on'] in failed_steps:
                print(f"\nSKIPPING Step {step['step_id']}: Dependency failed")
                failed_steps.add(step['step_id'])
                continue
            if step.get('depends_on') and step['depends_on'] not in completed_steps:
                print(f"\nWAITING: Step {step['step_id']} depends on Step {step['depends_on']}")
                continue
            if interactive and i > 1:
                print(f"\n{'='*70}")
                print(f"Progress: {len(completed_steps)}/{total_steps} steps completed")
                user_input = input("\nPress Enter to continue to next step (or 'q' to quit): ").strip().lower()
                if user_input == 'q':
                    print("\nWorkflow cancelled by user")
                    workflow['status'] = 'cancelled'
                    break

            # --- Placeholders fix ---
            try:
                step_to_run = dict(step)
                if 'params' in step:
                    step_to_run['params'] = self._replace_placeholders(step['params'], step_outputs)
                else:
                    step_to_run['params'] = {}
            except Exception as e:
                print(f"Warning: Failed to prepare step parameters: {e}")
                step_to_run = dict(step)  # Use original step if replacement fails

            # Execute step with error handling
            try:
                result = self.execute_step(step_to_run, workflow)
            except Exception as e:
                print(f"Critical error executing step {step.get('step_id', 'unknown')}: {e}")
                import traceback
                traceback.print_exc()
                failed_steps.add(step['step_id'])
                continue
            
            # Save relevant data for placeholder replacement
            try:
                if result.status == 'success' or result.status == ActionStatus.SUCCESS.value:
                    completed_steps.add(step['step_id'])
                    
                    # Collect metadata from execution result
                    if hasattr(result, 'metadata') and result.metadata:
                        for k, v in result.metadata.items():
                            if v:  # Only store non-empty values
                                step_outputs[k] = v
                    
                    # Special handling for extract_web_content
                    if step.get('action_type') == 'extract_web_content':
                        if hasattr(result, 'metadata') and result.metadata:
                            # Try to get web_content from metadata first
                            if 'web_content' in result.metadata:
                                step_outputs['web_content'] = result.metadata['web_content']
                            elif 'source_url' in result.metadata:
                                step_outputs['source_url'] = result.metadata['source_url']
                    
                    # Clear placeholder if it wasn't replaced (fallback)
                    if '{{web_content}}' in str(step_outputs.get('slides', [])):
                        print("Warning: web_content placeholder not replaced - using fallback")
                        step_outputs['web_content'] = "Content extraction failed or incomplete."
                        
                else:
                    failed_steps.add(step['step_id'])
                    print(f"\nStep {step['step_id']} failed!")
                    
                    if interactive:
                        try:
                            retry = input("Retry this step? (y/n): ").strip().lower()
                            if retry == 'y':
                                retry_result = self.execute_step(step_to_run, workflow)
                                if retry_result.status == 'success' or retry_result.status == ActionStatus.SUCCESS.value:
                                    completed_steps.add(step['step_id'])
                                    failed_steps.discard(step['step_id'])
                                    # Try to extract metadata from retry result
                                    if hasattr(retry_result, 'metadata') and retry_result.metadata:
                                        for k, v in retry_result.metadata.items():
                                            if v:
                                                step_outputs[k] = v
                                else:
                                    print("Retry also failed. Continuing...")
                            else:
                                print("Continuing to next step...")
                        except (KeyboardInterrupt, EOFError):
                            print("\nInput interrupted. Continuing workflow...")
                        except Exception as e:
                            print(f"Error during retry prompt: {e}. Continuing...")
            except Exception as e:
                print(f"Warning: Error processing step result: {e}")
                # Still mark as failed if we can't process the result
                if result.status != 'success' and result.status != ActionStatus.SUCCESS.value:
                    failed_steps.add(step['step_id'])
        workflow['end_time'] = datetime.now().isoformat()
        workflow['status'] = 'complete' if not failed_steps else 'partial' if completed_steps else 'failed'
        
        # Print summary
        try:
            self._print_workflow_summary(workflow, completed_steps, failed_steps)
        except Exception as e:
            print(f"Warning: Failed to print workflow summary: {e}")
    
    def _print_workflow_summary(self, workflow: Dict, completed: set, failed: set):
        """Print workflow execution summary with error handling"""
        try:
            print("\n" + "="*70)
            print("WORKFLOW EXECUTION SUMMARY")
            print("="*70)
            
            total = len(workflow.get('steps', []))
            completed_count = len(completed) if completed else 0
            failed_count = len(failed) if failed else 0
            
            print(f"\nWorkflow ID: {workflow.get('workflow_id', 'unknown')}")
            print(f"Topic: {workflow.get('topic', 'N/A')}")
            print(f"Status: {workflow.get('status', 'unknown').upper()}")
            print(f"\nTotal Steps: {total}")
            print(f"Completed: {completed_count}")
            print(f"Failed: {failed_count}")
            print(f"Skipped: {total - completed_count - failed_count}")
            
            if failed:
                print(f"\nFailed Steps:")
                for step_id in sorted(failed):
                    try:
                        step = next((s for s in workflow.get('steps', []) if s.get('step_id') == step_id), None)
                        if step:
                            print(f"   • Step {step_id}: {step.get('name', 'Unknown')}")
                        else:
                            print(f"   • Step {step_id}: (Step details not found)")
                    except Exception as e:
                        print(f"   • Step {step_id}: (Error retrieving step info: {e})")
            
            print("\n" + "="*70)
            
            # Save workflow report
            self._save_workflow_report(workflow)
        except Exception as e:
            print(f"Error printing workflow summary: {e}")
            import traceback
            traceback.print_exc()
    
    def _save_workflow_report(self, workflow: Dict):
        """Save workflow execution report to file with error handling"""
        try:
            report_dir = "logs/workflows"
            os.makedirs(report_dir, exist_ok=True)
            
            report_file = os.path.join(
                report_dir,
                f"{workflow.get('workflow_id', 'unknown')}_report.json"
            )
            
            report = {
                "workflow": workflow,
                "task_history": self.task_history
            }
            
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            print(f"\nWorkflow report saved: {report_file}")
        except Exception as e:
            print(f"Warning: Failed to save workflow report: {e}")
            import traceback
            traceback.print_exc()
    
    def demo_mode(self):
        """Run in demo mode with predefined workflow"""
        try:
            self.print_header()
        except Exception as e:
            print(f"Warning: Error printing header: {e}")
        
        # Get topic from user
        try:
            workflow = self.create_workflow()
        except Exception as e:
            print(f"Error creating workflow: {e}")
            import traceback
            traceback.print_exc()
            return
        
        # Display plan
        try:
            self.print_workflow_plan(workflow)
        except Exception as e:
            print(f"Warning: Error printing workflow plan: {e}")
        
        # Confirm execution
        try:
            print("\n" + "="*70)
            confirm = input("\nReady to execute workflow? (y/n): ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\n\nDemo cancelled by user")
            return
        except Exception as e:
            print(f"Error getting confirmation: {e}. Proceeding automatically...")
            confirm = 'y'
        
        if confirm != 'y':
            print("\nDemo cancelled")
            return
        
        # Execute workflow
        try:
            print("\nStarting workflow execution...")
            time.sleep(1)
            self.execute_workflow(workflow, interactive=False)
        except KeyboardInterrupt:
            print("\n\nWorkflow interrupted by user")
            workflow['status'] = 'cancelled'
        except Exception as e:
            print(f"\nCritical error during workflow execution: {e}")
            import traceback
            traceback.print_exc()
            workflow['status'] = 'error'
        
        # Final message
        try:
            print("\n" + "="*70)
            print("DEMO COMPLETED!")
            print("="*70)
            print("\nCheck the following:")
            print("  Desktop/agent_presentation/ - Your presentation folder")
            print("  logs/workflows/ - Detailed execution report")
            print("  screenshots/ - Error screenshots (if any)")
            print("="*70 + "\n")
        except Exception as e:
            print(f"Warning: Error printing final message: {e}")


def main():
    """Main entry point"""
    print("\n" + "="*70)
    print("COORDINATOR-EXECUTION AGENT INTEGRATION DEMO")
    print("="*70)
    print("\nThis demo simulates how the Coordinator Agent delegates")
    print("a complex multi-step task to the Execution Agent.")
    print("\nScenario: Create a research presentation about any topic")
    print("="*70)
    
    coordinator = CoordinatorInterface()
    
    try:
        coordinator.demo_mode()
    
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
    
    except Exception as e:
        print(f"\n\nDemo error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
