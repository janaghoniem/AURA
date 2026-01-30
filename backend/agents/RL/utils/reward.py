def compute_reward(execution_result: dict) -> float:
    reward = 0.0

    completed = execution_result.get("completed_tasks", {})
    total = len(completed)

    successes = sum(1 for s in completed.values() if s == "success")
    failures = sum(1 for s in completed.values() if s == "failed")

    reward += successes * 0.5
    reward -= failures * 0.7

    if execution_result.get("needs_refinement"):
        reward -= 0.4

    if successes == total and total > 0:
        reward += 1.0  # full success bonus

    return reward
