"""
Data Models Module
Structured data classes for Execution Agent

Author: Accessibility AI Team
Version: 1.0.0
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List


@dataclass
class ExecutionTask:
    """Structured task from Coordinator"""
    action_type: str
    context: str
    strategy: str
    params: Dict[str, Any]
    task_id: Optional[str] = None
    priority: str = "normal"
    timeout: int = 30
    retry_count: int = 3
    fallback_strategies: Optional[List[str]] = None
    
    def to_dict(self):
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class ExecutionResult:
    """Result returned to Coordinator"""
    status: str
    task_id: Optional[str]
    context: str
    action: str
    details: str
    logs: List[str]
    timestamp: str
    duration: float
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    screenshot_path: Optional[str] = None
    
    def to_dict(self):
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class VisionResult:
    """Result from Vision Layer"""
    element_found: bool
    coordinates: Optional[tuple]
    confidence: float
    text_detected: Optional[str]
    method_used: str  # "uia", "ocr", "cv"
    
    def to_dict(self):
        """Convert to dictionary"""
        return asdict(self)
