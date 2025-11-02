from exec_agent_main import ExecutionAgent
import json
import os

def run_task(agent, task_dict, context=None):
    # Optionally handle placeholder replacement/context (advanced)
    # For simple tasks, just send as-is:
    result = agent.execute_from_dict(task_dict)
    print(f"\nResult for task {task_dict.get('task_id')}:")
    print(json.dumps(result, indent=2))
    # Store outputs if needed
    if context is not None and result.get("metadata"):
        context.update(result["metadata"])
    return result

if __name__ == "__main__":
    agent = ExecutionAgent()
    context = {}
    workflow_file = "workflow.json" if os.path.exists("workflow.json") else "task.json"

    with open(workflow_file, "r") as f:
        data = json.load(f)

    # If it's a list, treat as workflow
    if isinstance(data, list):
        print(f"Loaded workflow with {len(data)} tasks.")
        for task_dict in data:
            # (Optional) Replace {{placeholder}} with context output for advanced workflows
            task_json = json.dumps(task_dict)
            for k, v in context.items():
                task_json = task_json.replace(f"{{{{{k}}}}}", str(v))
            task_dict = json.loads(task_json)
            result = run_task(agent, task_dict, context)
    else:
        print("Loaded single task.")
        run_task(agent, data)