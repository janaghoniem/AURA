import numpy as np

def encode_state(context: dict) -> np.ndarray:
    """
    Converts coordinator execution context into 12-dim state vector
    """
    return np.array([
        context.get("num_tasks_total", 0),
        context.get("num_tasks_completed", 0),
        context.get("num_failed", 0),
        context.get("num_refinements", 0),
        context.get("has_parallel", 0),
        context.get("has_dependencies", 0),
        context.get("memory_hits", 0),
        context.get("retry_count", 0),
        context.get("timeout_ratio", 0.0),
        context.get("is_root_task", 1),
        context.get("avg_task_latency", 0.0),
        context.get("progress_ratio", 0.0),
    ], dtype=np.float32)
