"""
Safety Layer Module
Handles risk assessment, confirmations, undo queue, audit logging

Author: Accessibility AI Team
Version: 1.0.0
"""

import json
from datetime import datetime
from typing import Dict, List

# from backend.agents.execution_agent.core.exec_agent_config import Config, RiskLevel
from ..core.exec_agent_config import Config, RiskLevel, StatusCode


class SafetyLayer:
    """
    Handles risk assessment, confirmations, undo queue, audit logging
    """
    
    def __init__(self, logger):
        self.logger = logger
        self.undo_queue = []
        self.max_undo_history = Config.MAX_UNDO_HISTORY
        self.audit_log = []
        self.risk_rules = Config.RISK_RULES
    
    def assess_risk(self, action: str, params: Dict) -> RiskLevel:
        """
        Assess risk level of action
        
        Args:
            action: Action type
            params: Action parameters
        
        Returns:
            RiskLevel enum
        """
        action_lower = action.lower()
        
        # Check for critical keywords
        for keyword, risk in self.risk_rules.items():
            if keyword in action_lower:
                self.logger.info(f"Risk assessment: {action} -> {risk.value}")
                return risk
        
        # Default to MEDIUM for unknown actions
        self.logger.info(f"Risk assessment: {action} -> MEDIUM (default)")
        return RiskLevel.MEDIUM
    
    def requires_confirmation(self, risk: RiskLevel) -> bool:
        """
        Check if action requires user confirmation
        
        Args:
            risk: RiskLevel
        
        Returns:
            True if confirmation needed
        """
        return risk in [RiskLevel.HIGH, RiskLevel.CRITICAL]
    
    def add_to_undo_queue(self, action_snapshot: Dict):
        """
        Add action to undo queue
        
        Args:
            action_snapshot: Dictionary with action details
        """
        self.undo_queue.append({
            "timestamp": datetime.now().isoformat(),
            "action": action_snapshot
        })
        
        # Limit queue size
        if len(self.undo_queue) > self.max_undo_history:
            self.undo_queue.pop(0)
        
        self.logger.debug(f"Added to undo queue: {action_snapshot.get('action_type')}")
    
    def get_undo_queue(self) -> List[Dict]:
        """
        Get current undo queue
        
        Returns:
            List of action snapshots
        """
        return self.undo_queue.copy()
    
    def clear_undo_queue(self):
        """Clear undo queue"""
        self.undo_queue.clear()
        self.logger.info("Undo queue cleared")
    
    def audit_log_action(self, action: str, status: str, details: Dict):
        """
        Log action to audit trail
        
        Args:
            action: Action name
            status: Action status
            details: Additional details
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "status": status,
            "details": details
        }
        
        self.audit_log.append(entry)
        
        # Persist to file
        try:
            audit_file = Config.get_audit_file()
            with open(audit_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            self.logger.debug(f"Audit log entry written: {action}")
        except Exception as e:
            self.logger.error(f"Failed to write audit log: {e}")
    
    def get_audit_log(self) -> List[Dict]:
        """
        Get current session audit log
        
        Returns:
            List of audit entries
        """
        return self.audit_log.copy()
    
    def validate_action(self, action: str, params: Dict) -> tuple:
        """
        Validate action before execution
        
        Args:
            action: Action type
            params: Action parameters
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check for required parameters
        if not action:
            return False, "Action type is required"
        
        # Add more validation rules as needed
        
        return True, None
