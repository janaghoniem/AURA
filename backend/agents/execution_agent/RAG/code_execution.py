# ============================================================================
# RAG Integration Layer - Updated for Coordinator Agent Compatibility
# ============================================================================
# This file bridges the coordinator agent's ActionTask format with the RAG system

import json
import logging
import asyncio
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

# ============================================================================
# Task Models (matching coordinator_agent.py)
# ============================================================================

class ActionTask:
    """Task format from coordinator agent"""
    def __init__(
        self,
        task_id: str,
        ai_prompt: str,
        device: str,  # "desktop" or "mobile"
        context: str,  # "local" or "web"
        target_agent: str,  # "action" or "reasoning"
        extra_params: Optional[Dict[str, Any]] = None,
        depends_on: Optional[str] = None
    ):
        self.task_id = task_id
        self.ai_prompt = ai_prompt
        self.device = device
        self.context = context
        self.target_agent = target_agent
        self.extra_params = extra_params or {}
        self.depends_on = depends_on
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ActionTask':
        """Create ActionTask from dictionary"""
        return cls(
            task_id=data.get('task_id', ''),
            ai_prompt=data.get('ai_prompt', ''),
            device=data.get('device', 'desktop'),
            context=data.get('context', 'local'),
            target_agent=data.get('target_agent', 'action'),
            extra_params=data.get('extra_params', {}),
            depends_on=data.get('depends_on')
        )
    
    def dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'task_id': self.task_id,
            'ai_prompt': self.ai_prompt,
            'device': self.device,
            'context': self.context,
            'target_agent': self.target_agent,
            'extra_params': self.extra_params,
            'depends_on': self.depends_on
        }

class TaskResult:
    """Result format for coordinator agent"""
    def __init__(
        self,
        task_id: str,
        status: str,  # "success", "failed", "pending"
        content: Optional[str] = None,
        error: Optional[str] = None
    ):
        self.task_id = task_id
        self.status = status
        self.content = content
        self.error = error
    
    def dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'task_id': self.task_id,
            'status': self.status,
            'content': self.content,
            'error': self.error
        }

# ============================================================================
# RAG Task Adapter - Converts ActionTask to RAG-compatible format
# ============================================================================

class RAGTaskAdapter:
    """Adapts coordinator ActionTask to RAG system requirements"""
    
    @staticmethod
    def build_rag_query(task: ActionTask) -> str:
        """
        Convert ActionTask to enhanced query string for RAG system
        
        Args:
            task: ActionTask from coordinator
            
        Returns:
            Enhanced query string with context
        """
        # Start with base prompt
        query_parts = [task.ai_prompt]
        
        # Add context from extra_params
        if task.extra_params:
            # Add app name if specified
            if 'app_name' in task.extra_params:
                query_parts.append(f"Application: {task.extra_params['app_name']}")
            
            # Add URL if web context
            if 'url' in task.extra_params:
                query_parts.append(f"URL: {task.extra_params['url']}")
            
            # Add file path if specified
            if 'file_path' in task.extra_params:
                query_parts.append(f"File: {task.extra_params['file_path']}")
            
            # Add text to type if specified
            if 'text_to_type' in task.extra_params:
                query_parts.append(f"Text to type: {task.extra_params['text_to_type']}")
            
            # Add input content from previous tasks
            if 'input_content' in task.extra_params:
                query_parts.append(f"Input data: {task.extra_params['input_content'][:200]}...")
        
        # Add device/context hints
        if task.context == "web":
            query_parts.append("(web automation)")
        elif task.context == "local":
            query_parts.append("(desktop automation)")
        
        # Join all parts
        enhanced_query = " | ".join(query_parts)
        
        logger.debug(f"📝 Enhanced query: {enhanced_query[:100]}...")
        return enhanced_query
    
    @staticmethod
    def execution_result_to_task_result(
        task: ActionTask,
        execution_result
    ) -> TaskResult:
        """
        Convert RAG ExecutionResult to coordinator TaskResult
        
        Args:
            task: Original ActionTask
            execution_result: ExecutionResult from sandbox
            
        Returns:
            TaskResult for coordinator
        """
        # Determine status
        if execution_result.validation_passed and execution_result.security_passed:
            status = "success"
            content = execution_result.stdout
            error = None
        else:
            status = "failed"
            content = None
            # Combine all errors
            errors = []
            if execution_result.validation_errors:
                errors.extend(execution_result.validation_errors)
            if execution_result.security_violations:
                errors.extend(execution_result.security_violations)
            if execution_result.stderr:
                errors.append(f"stderr: {execution_result.stderr[:200]}")
            error = " | ".join(errors)
        
        return TaskResult(
            task_id=task.task_id,
            status=status,
            content=content,
            error=error
        )

# ============================================================================
# Updated RAG Integration Class
# ============================================================================

class CoordinatorRAGBridge:
    """
    Bridge between Coordinator Agent and RAG System
    Handles ActionTask execution via RAG pipeline
    """
    
    def __init__(self, rag_system, sandbox_pipeline):
        """
        Initialize bridge
        
        Args:
            rag_system: RAGSystem instance
            sandbox_pipeline: SandboxExecutionPipeline instance
        """
        self.rag = rag_system
        self.sandbox = sandbox_pipeline
        self.adapter = RAGTaskAdapter()
    
    async def execute_action_task(
        self,
        task: ActionTask,
        max_retries: int = 2,
        enable_cache: bool = True
    ) -> TaskResult:
        """
        Execute a single ActionTask using RAG pipeline
        
        Args:
            task: ActionTask from coordinator
            max_retries: Maximum retry attempts
            enable_cache: Whether to use action cache
            
        Returns:
            TaskResult for coordinator
        """
        logger.info(f"🔄 Processing task {task.task_id}: {task.ai_prompt[:50]}...")
        
        # Only process action tasks (not reasoning tasks)
        if task.target_agent != "action":
            logger.warning(f"⚠️ Task {task.task_id} is not an action task, skipping RAG")
            return TaskResult(
                task_id=task.task_id,
                status="failed",
                error="Not an action task - should be handled by reasoning agent"
            )
        
        # Build enhanced query for RAG
        rag_query = self.adapter.build_rag_query(task)
        
        # Execute through RAG + Sandbox pipeline
        attempt = 0
        error_context = ""
        start_context_index = 0
        
        while attempt < max_retries:
            attempt += 1
            logger.info(f"📍 Attempt {attempt}/{max_retries} for task {task.task_id}")
            
            # Generate code using RAG
            enhanced_query = rag_query
            if error_context:
                enhanced_query += f"\n\nPrevious attempt failed: {error_context}"
                enhanced_query += "\nPlease provide an alternative approach."
            
            try:
                rag_result = self.rag.generate_code(
                    enhanced_query,
                    cache_key=task.ai_prompt,  # Use original prompt for cache
                    start_context_index=start_context_index,
                    num_contexts=self.rag.config.top_k
                )
                
                generated_code = rag_result.get('code', '')
                
                if not generated_code:
                    logger.warning(f"⚠️ No code generated for task {task.task_id}")
                    
                    if rag_result.get('contexts_used', 0) == 0:
                        logger.error("❌ No more contexts available")
                        break
                    
                    start_context_index += self.rag.config.top_k
                    continue
                
                logger.debug(f"✅ Generated {len(generated_code)} chars of code")
                
                # Execute in sandbox
                exec_result = self.sandbox.execute_code(
                    code=generated_code,
                    use_docker=False,
                    retry_on_failure=False
                )
                
                # Check result
                if exec_result.validation_passed and exec_result.security_passed:
                    logger.info(f"✅ Task {task.task_id} completed successfully")
                    
                    # Cache if enabled
                    if enable_cache:
                        self.sandbox.action_cache.store_action(
                            query=task.ai_prompt,
                            code=generated_code,
                            execution_result=exec_result
                        )
                    
                    return self.adapter.execution_result_to_task_result(task, exec_result)
                
                # Failed - prepare for retry
                logger.warning(f"⚠️ Execution failed (attempt {attempt})")
                
                error_context = f"Errors: {', '.join(exec_result.validation_errors)}"
                if exec_result.stderr:
                    error_context += f" | stderr: {exec_result.stderr[:200]}"
                
                start_context_index += self.rag.config.top_k
                
            except Exception as e:
                logger.error(f"❌ Exception during RAG execution: {e}")
                error_context = str(e)
        
        # All retries exhausted
        logger.error(f"❌ Task {task.task_id} failed after {max_retries} attempts")
        return TaskResult(
            task_id=task.task_id,
            status="failed",
            error=f"Failed after {max_retries} attempts: {error_context}"
        )
    
    async def execute_task_batch(
        self,
        tasks: list,
        enable_cache: bool = True
    ) -> Dict[str, TaskResult]:
        """
        Execute multiple ActionTasks (handles dependencies internally)
        
        Args:
            tasks: List of ActionTask dictionaries or objects
            enable_cache: Whether to use action cache
            
        Returns:
            Dictionary mapping task_id to TaskResult
        """
        results = {}
        task_outputs = {}  # Store outputs for dependent tasks
        
        # Convert dicts to ActionTask objects if needed
        action_tasks = []
        for task_data in tasks:
            if isinstance(task_data, dict):
                action_tasks.append(ActionTask.from_dict(task_data))
            else:
                action_tasks.append(task_data)
        
        logger.info(f"📋 Executing batch of {len(action_tasks)} tasks")
        
        for task in action_tasks:
            # Check dependencies
            if task.depends_on:
                dep_ids = task.depends_on.split(",")
                dependencies_met = all(
                    results.get(dep_id.strip(), TaskResult(dep_id.strip(), "failed")).status == "success"
                    for dep_id in dep_ids
                )
                
                if not dependencies_met:
                    logger.warning(f"⏭️ Skipping {task.task_id} - dependencies not met")
                    results[task.task_id] = TaskResult(
                        task_id=task.task_id,
                        status="failed",
                        error="Dependency failed"
                    )
                    continue
            
            # Inject dependent task outputs
            if task.extra_params.get("input_from"):
                input_task_id = task.extra_params["input_from"]
                if input_task_id in task_outputs:
                    task.extra_params["input_content"] = task_outputs[input_task_id]
            
            # Execute task
            result = await self.execute_action_task(task, enable_cache=enable_cache)
            results[task.task_id] = result
            
            # Store output for dependent tasks
            if result.content:
                task_outputs[task.task_id] = result.content
            
            # Stop on failure (optional - can be changed)
            if result.status == "failed":
                logger.error(f"❌ Batch execution stopped at {task.task_id}")
                break
        
        logger.info(f"✅ Batch execution complete: {len(results)} tasks processed")
        return results

# ============================================================================
# Execution Agent Integration
# ============================================================================

async def start_execution_agent_with_rag(broker_instance, rag_system, sandbox_pipeline):
    """
    Start execution agent that handles ActionTasks from coordinator
    
    Args:
        broker_instance: Message broker instance
        rag_system: Initialized RAGSystem
        sandbox_pipeline: Initialized SandboxExecutionPipeline
    """
    # Create bridge
    bridge = CoordinatorRAGBridge(rag_system, sandbox_pipeline)
    
    async def handle_execution_request(message):
        """
        Handle execution request from coordinator
        
        Message format:
        {
            "message_type": "EXECUTION_REQUEST",
            "sender": "COORDINATOR",
            "receiver": "EXECUTION",
            "task_id": "task_1",
            "session_id": "session_123",
            "payload": {
                "task_id": "task_1",
                "ai_prompt": "Open Notepad",
                "device": "desktop",
                "context": "local",
                "target_agent": "action",
                "extra_params": {...},
                "depends_on": null
            }
        }
        """
        try:
            # Extract task from message
            task_data = message.payload
            task = ActionTask.from_dict(task_data)
            
            logger.info(f"🎯 Execution agent received task {task.task_id}")
            
            # Execute task via RAG pipeline
            result = await bridge.execute_action_task(
                task=task,
                max_retries=2,
                enable_cache=True
            )
            
            # Send result back to coordinator
            from agents.utils.protocol import AgentMessage, MessageType, AgentType, Channels
            
            response_msg = AgentMessage(
                message_type=MessageType.EXECUTION_RESULT,
                sender=AgentType.EXECUTION,
                receiver=AgentType.COORDINATOR,
                session_id=message.session_id,
                task_id=task.task_id,
                response_to=message.message_id,
                payload=result.dict()
            )
            
            await broker_instance.publish(Channels.EXECUTION_TO_COORDINATOR, response_msg)
            logger.info(f"✅ Sent result for task {task.task_id}: {result.status}")
            
        except Exception as e:
            logger.error(f"❌ Error processing execution request: {e}")
            
            # Send error response
            error_result = TaskResult(
                task_id=message.task_id or "unknown",
                status="failed",
                error=str(e)
            )
            
            error_msg = AgentMessage(
                message_type=MessageType.EXECUTION_RESULT,
                sender=AgentType.EXECUTION,
                receiver=AgentType.COORDINATOR,
                session_id=message.session_id,
                task_id=message.task_id,
                response_to=message.message_id,
                payload=error_result.dict()
            )
            
            await broker_instance.publish(Channels.EXECUTION_TO_COORDINATOR, error_msg)
    
    # Subscribe to execution requests from coordinator
    from agents.utils.protocol import Channels
    broker_instance.subscribe(Channels.COORDINATOR_TO_EXECUTION, handle_execution_request)
    
    logger.info("✅ Execution Agent started with RAG integration")
    
    while True:
        await asyncio.sleep(1)

# ============================================================================
# Usage Example
# ============================================================================

async def example_usage():
    """Example of how to use the bridge"""
    from code_generation import RAGSystem, RAGConfig
    from code_execution import SandboxExecutionPipeline, SandboxConfig
    
    # Initialize RAG system
    rag_config = RAGConfig(library_name="pywinauto")
    rag_system = RAGSystem(rag_config)
    rag_system.initialize()
    
    # Initialize sandbox
    sandbox_config = SandboxConfig()
    sandbox_pipeline = SandboxExecutionPipeline(sandbox_config)
    
    # Create bridge
    bridge = CoordinatorRAGBridge(rag_system, sandbox_pipeline)
    
    # Example task from coordinator
    task_data = {
        "task_id": "task_1",
        "ai_prompt": "Open Notepad application",
        "device": "desktop",
        "context": "local",
        "target_agent": "action",
        "extra_params": {"app_name": "notepad.exe"},
        "depends_on": None
    }
    
    task = ActionTask.from_dict(task_data)
    
    # Execute task
    result = await bridge.execute_action_task(task)
    
    print(f"Task {result.task_id}: {result.status}")
    if result.error:
        print(f"Error: {result.error}")
    if result.content:
        print(f"Output: {result.content[:100]}...")

if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())

# ============================================================================
# Main Integration Setup
# ============================================================================
async def initialize_execution_agent_for_server(broker_instance):
    """
    Server-compatible initialization for execution agent with RAG system
    This handles missing dependencies gracefully
    
    Args:
        broker_instance: Message broker instance from server
    """
    from dotenv import load_dotenv
    load_dotenv()
    
    # Prevent duplicate subscriptions
    if hasattr(broker_instance, '_rag_execution_subscribed'):
        logger.warning("⚠️ RAG Execution agent already subscribed, skipping")
        return
    broker_instance._rag_execution_subscribed = True
    
    try:
        # Try to import RAG components
        from agents.execution_agent.RAG.code_generation import RAGSystem, RAGConfig
        
        # Create stub sandbox if not available
        class StubSandbox:
            """Stub sandbox for when full sandbox is not available"""
            def execute_code(self, code, use_docker=False, retry_on_failure=False):
                logger.warning("⚠️ Using stub sandbox - code will not execute")
                class StubResult:
                    validation_passed = False
                    security_passed = False
                    validation_errors = ["Sandbox not initialized"]
                    security_violations = []
                    stdout = ""
                    stderr = "Sandbox unavailable"
                return StubResult()
        
        # Initialize RAG system
        try:
            logger.info("🔧 Initializing RAG system...")
            rag_config = RAGConfig(library_name="pywinauto")
            rag_system = RAGSystem(rag_config)
            rag_system.initialize()
            logger.info("✅ RAG system ready")
        except Exception as e:
            logger.warning(f"⚠️ Failed to initialize RAG: {e}")
            rag_system = None
        
        # Initialize sandbox (use stub if not available)
        try:
            logger.info("🔧 Initializing sandbox pipeline...")
            from agents.execution_agent.RAG.code_execution import SandboxExecutionPipeline, SandboxConfig
            sandbox_config = SandboxConfig(timeout_seconds=30, enable_security_check=True)
            sandbox_pipeline = SandboxExecutionPipeline(sandbox_config)
            logger.info("✅ Sandbox pipeline ready")
        except ImportError:
            logger.warning("⚠️ Sandbox not available, using stub")
            sandbox_pipeline = StubSandbox()
        
        # If RAG is available, start with RAG bridge
        if rag_system:
            logger.info("🚀 Starting execution agent with RAG integration...")
            await start_execution_agent_with_rag(broker_instance, rag_system, sandbox_pipeline)
        else:
            logger.warning("⚠️ RAG not available - execution agent will be limited")
            # Fall back to simple execution or stub
            await start_simple_execution_agent(broker_instance)
    
    except ImportError as e:
        logger.error(f"❌ Failed to import RAG components: {e}")
        logger.info("📦 Starting fallback execution agent...")
        await start_simple_execution_agent(broker_instance)


async def start_simple_execution_agent(broker_instance):
    """
    Simple execution agent that acts as a fallback
    Acknowledges tasks but doesn't execute RAG code
    
    Args:
        broker_instance: Message broker instance
    """
    from agents.utils.protocol import AgentMessage, MessageType, AgentType, Channels
    
    async def handle_execution_request(message):
        """Handle execution request with simple fallback"""
        try:
            task_data = message.payload
            task_id = task_data.get('task_id', 'unknown')
            ai_prompt = task_data.get('ai_prompt', '')
            
            logger.info(f"🎯 Fallback execution agent received task {task_id}: {ai_prompt[:50]}...")
            
            # Create result
            result = {
                'task_id': task_id,
                'status': 'pending',
                'content': f"Task '{ai_prompt}' awaiting RAG execution",
                'error': None
            }
            
            # Send response back to coordinator
            response_msg = AgentMessage(
                message_type=MessageType.EXECUTION_RESULT,
                sender=AgentType.EXECUTION,
                receiver=AgentType.COORDINATOR,
                session_id=message.session_id,
                task_id=task_id,
                response_to=message.message_id,
                payload=result
            )
            
            await broker_instance.publish(Channels.EXECUTION_TO_COORDINATOR, response_msg)
            logger.info(f"⏳ Sent pending status for task {task_id}")
            
        except Exception as e:
            logger.error(f"❌ Error in fallback execution: {e}")
    
    # Subscribe to execution requests
    broker_instance.subscribe(Channels.COORDINATOR_TO_EXECUTION, handle_execution_request)
    logger.info("✅ Fallback Execution Agent started")
    
    while True:
        await asyncio.sleep(1)

# Example integration in your main.py or agent startup:
"""
from agents.execution_agent.rag_integration import initialize_execution_agent

async def main():
    # Start all agents
    await asyncio.gather(
        initialize_execution_agent(),  # RAG-powered execution agent
        # ... other agents ...
    )

if __name__ == "__main__":
    asyncio.run(main())
"""