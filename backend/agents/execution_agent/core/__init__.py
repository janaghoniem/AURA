from .exec_agent_config import Config, ExecutionContext, ActionStatus, RiskLevel, StatusCode
from .exec_agent_models import ExecutionTask, ExecutionResult, VisionResult
from .exec_agent_deps import (
    check_dependencies,
    get_missing_dependencies,
    PYWINAUTO_AVAILABLE,
    PYAUTOGUI_AVAILABLE,
    SELENIUM_AVAILABLE,
    OCR_AVAILABLE
)

# Provide a lazy accessor to obtain ExecutionAgent when needed
def get_execution_agent_class():
    """
    Lazily import and return ExecutionAgent class to avoid circular imports
    Usage: ExecutionAgent = get_execution_agent_class()
    """
    from .exec_agent_main import ExecutionAgent
    return ExecutionAgent

__all__ = [
    'Config',
    'ExecutionContext',
    'ActionStatus',
    'RiskLevel',
    'StatusCode',
    'ExecutionTask',
    'ExecutionResult',
    'VisionResult',
    'check_dependencies',
    'get_missing_dependencies',
    'PYWINAUTO_AVAILABLE',
    'PYAUTOGUI_AVAILABLE',
    'SELENIUM_AVAILABLE',
    'OCR_AVAILABLE',
    "get_execution_agent_class"
]