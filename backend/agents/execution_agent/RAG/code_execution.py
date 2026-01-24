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
        device: str,
        context: str,
        target_agent: str,
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
        status: str,
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
# RAG Task Adapter
# ============================================================================

class RAGTaskAdapter:
    """Adapts coordinator ActionTask to RAG system requirements"""
    
    @staticmethod
    def build_rag_query(task: ActionTask) -> str:
        """Convert ActionTask to enhanced query string for RAG system"""
        query_parts = [task.ai_prompt]
        
        if task.extra_params:
            if 'app_name' in task.extra_params:
                query_parts.append(f"Application: {task.extra_params['app_name']}")
            if 'url' in task.extra_params:
                query_parts.append(f"URL: {task.extra_params['url']}")
            if 'file_path' in task.extra_params:
                query_parts.append(f"File: {task.extra_params['file_path']}")
            if 'text_to_type' in task.extra_params:
                query_parts.append(f"Text to type: {task.extra_params['text_to_type']}")
            if 'input_content' in task.extra_params:
                query_parts.append(f"Input data: {task.extra_params['input_content'][:200]}...")
        
        if task.context == "web":
            query_parts.append("(web automation)")
        elif task.context == "local":
            query_parts.append("(desktop automation)")
        
        enhanced_query = " | ".join(query_parts)
        logger.debug(f"📝 Enhanced query: {enhanced_query[:100]}...")
        return enhanced_query
    
    @staticmethod
    def execution_result_to_task_result(task: ActionTask, execution_result) -> TaskResult:
        """Convert RAG ExecutionResult to coordinator TaskResult"""
        if execution_result.validation_passed and execution_result.security_passed:
            status = "success"
            content = execution_result.stdout
            error = None
        else:
            status = "failed"
            content = None
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
# Coordinator RAG Bridge
# ============================================================================

class CoordinatorRAGBridge:
    """Bridge between Coordinator Agent and RAG System"""
    
    def __init__(self, rag_system, sandbox_pipeline):
        self.rag = rag_system
        self.sandbox = sandbox_pipeline
        self.adapter = RAGTaskAdapter()
    
    async def execute_action_task(
        self,
        task: ActionTask,
        max_retries: int = 2,
        enable_cache: bool = False,  # Enable cache by default
        cache_threshold: float = 0.85
    ) -> TaskResult:
        """
        Execute a single ActionTask using RAG pipeline with cache support
        
        Args:
            task: ActionTask from coordinator
            max_retries: Maximum retry attempts
            enable_cache: Whether to check/use cache
            cache_threshold: Similarity threshold for cache hit (0.85 = 85%)
            
        Returns:
            TaskResult for coordinator
        """
        logger.info(f"🔄 Processing task {task.task_id}: {task.ai_prompt[:50]}...")
        
        # Only process action tasks
        if task.target_agent != "action":
            logger.warning(f"⚠️ Task {task.task_id} is not an action task, skipping RAG")
            return TaskResult(
                task_id=task.task_id,
                status="failed",
                error="Not an action task - should be handled by reasoning agent"
            )
        
        # Build enhanced query for RAG
        rag_query = self.adapter.build_rag_query(task)
        
        # ========================================================================
        # STEP 0: CHECK CACHE FIRST (if enabled and available)
        # ========================================================================
        if enable_cache and hasattr(self.sandbox, 'action_cache'):
            try:
                logger.info(f"🔍 Checking cache for task {task.task_id}...")
                cached_action = self.sandbox.action_cache.search_cache(
                    rag_query,  # Use enhanced query for better matching
                    threshold=cache_threshold
                )
                
                if cached_action:
                    logger.info(f"✅ CACHE HIT! Similarity: {cached_action['similarity']:.2%}")
                    logger.info(f"⚡ Skipping RAG + Sandbox - using validated code!")
                    
                    # Execute cached code directly (already validated)
                    import subprocess
                    import tempfile
                    import sys
                    import time
                    
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                        f.write(cached_action['code'])
                        temp_file = f.name
                    
                    try:
                        start_time = time.time()
                        result = subprocess.run(
                            [sys.executable, temp_file],
                            capture_output=True,
                            text=True,
                            timeout=30
                        )
                        execution_time = time.time() - start_time
                        
                        # Create execution result
                        from agents.execution_agent.RAG.execution import ExecutionResult, ExecutionStatus
                        from datetime import datetime
                        import hashlib
                        
                        exec_result = ExecutionResult(
                            status=ExecutionStatus.SUCCESS if result.returncode == 0 else ExecutionStatus.FAILED,
                            exit_code=result.returncode,
                            stdout=result.stdout,
                            stderr=result.stderr,
                            execution_time=execution_time,
                            timestamp=datetime.now().isoformat(),
                            validation_passed=True,  # Already validated when cached
                            validation_errors=[],
                            security_passed=True,    # Already validated when cached
                            security_violations=[],
                            code_hash=cached_action['metadata']['code_hash']
                        )
                        
                        logger.info(f"✅ Cached code executed in {execution_time:.3f}s")
                        
                        # Convert to TaskResult
                        return self.adapter.execution_result_to_task_result(task, exec_result)
                        
                    except Exception as e:
                        logger.warning(f"⚠️ Cached code execution failed: {e}")
                        logger.info("🔄 Falling back to RAG generation...")
                        # Continue to RAG flow below
                    finally:
                        import os
                        try:
                            os.unlink(temp_file)
                        except:
                            pass
                else:
                    logger.info(f"❌ Cache miss - proceeding with RAG generation")
                    
            except Exception as cache_error:
                logger.warning(f"⚠️ Cache check failed: {cache_error}")
                logger.info("🔄 Proceeding with RAG generation...")
                # Continue to RAG flow below
        
        # ========================================================================
        # CACHE MISS OR DISABLED - FULL RAG + SANDBOX FLOW
        # ========================================================================
        attempt = 0
        error_context = ""
        start_context_index = 0
        
        while attempt < max_retries:
            attempt += 1
            logger.info(f"📍 Attempt {attempt}/{max_retries} for task {task.task_id}")
            
            # Build enhanced query with error context if retry
            enhanced_query = rag_query
            if error_context:
                enhanced_query += f"\n\nPrevious attempt failed: {error_context}"
                enhanced_query += "\nPlease provide an alternative approach."
            
            try:
                # Step 1: Generate code using RAG
                logger.info(f"🤖 Generating code with RAG...")
                rag_result = self.rag.generate_code(
                    enhanced_query,
                    cache_key=task.ai_prompt,  # Use original prompt for cache key
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
                
                logger.info(f"✅ Generated {len(generated_code)} chars of code")
                logger.debug(f"Generated code preview: {generated_code[:200]}...")
                
                # Step 2: Execute in LOCAL sandbox
                logger.info(f"🔧 Executing code in local sandbox...")
                exec_result = self.sandbox.execute_code(
                    code=generated_code,
                    use_docker=False,  # ALWAYS use local sandbox
                    retry_on_failure=False
                )
                
                # Step 3: Check execution result
                if exec_result.validation_passed and exec_result.security_passed:
                    logger.info(f"✅ Task {task.task_id} completed successfully")
                    
                    # ============================================================
                    # CACHE THE SUCCESSFUL RESULT (if cache enabled and available)
                    # ============================================================
                    if enable_cache and hasattr(self.sandbox, 'action_cache'):
                        try:
                            logger.info(f"💾 Caching validated action...")
                            self.sandbox.action_cache.store_action(
                                query=rag_query,  # Use enhanced query for better future matching
                                code=generated_code,
                                execution_result=exec_result
                            )
                            logger.info(f"✅ Action cached successfully")
                        except Exception as cache_error:
                            logger.warning(f"⚠️ Failed to cache action: {cache_error}")
                            # Don't fail the task if caching fails
                    
                    return self.adapter.execution_result_to_task_result(task, exec_result)
                
                # Execution failed - prepare for retry
                logger.warning(f"⚠️ Execution failed (attempt {attempt})")
                
                error_context = f"Errors: {', '.join(exec_result.validation_errors)}"
                if exec_result.stderr:
                    error_context += f" | stderr: {exec_result.stderr[:200]}"
                
                logger.debug(f"Error context for retry: {error_context}")
                
                start_context_index += self.rag.config.top_k
                
            except Exception as e:
                logger.error(f"❌ Exception during RAG execution: {e}")
                import traceback
                logger.debug(f"Traceback: {traceback.format_exc()}")
                error_context = str(e)
        
        # All retries exhausted
        logger.error(f"❌ Task {task.task_id} failed after {max_retries} attempts")
        return TaskResult(
            task_id=task.task_id,
            status="failed",
            error=f"Failed after {max_retries} attempts: {error_context}"
        )

# ============================================================================
# Execution Agent Integration
# ============================================================================

async def start_execution_agent_with_rag(broker_instance, rag_system, sandbox_pipeline):
    """Start execution agent that handles ActionTasks from coordinator"""
    bridge = CoordinatorRAGBridge(rag_system, sandbox_pipeline)
    
    async def handle_execution_request(message):
        """Handle execution request from coordinator"""
        try:
            task_data = message.payload
            task = ActionTask.from_dict(task_data)
            
            logger.info(f"🎯 Execution agent received task {task.task_id}")
            
            result = await bridge.execute_action_task(
                task=task,
                max_retries=2,
                enable_cache=False  # Disable cache to avoid ChromaDB errors
            )

            # FIX: Ensure result dict has task_id
            result_dict = result.dict()
            if "task_id" not in result_dict:
                result_dict["task_id"] = task.task_id
            
            # FIX: Use correct MessageType
            from agents.utils.protocol import AgentMessage, MessageType, AgentType, Channels
            
            response_msg = AgentMessage(
                message_type=MessageType.EXECUTION_RESPONSE,  # Changed from EXECUTION_RESULT
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

            task_id = message.task_id or getattr(message.payload, 'task_id', 'unknown')
            
            error_result = TaskResult(
                task_id=task_id,
                status="failed",
                error=str(e)
            )
            
            from agents.utils.protocol import AgentMessage, MessageType, AgentType, Channels
            
            error_msg = AgentMessage(
                message_type=MessageType.EXECUTION_RESPONSE,
                sender=AgentType.EXECUTION,
                receiver=AgentType.COORDINATOR,
                session_id=message.session_id,
                task_id=message.task_id,
                response_to=message.message_id,
                payload=error_result.dict()
            )
            
            await broker_instance.publish(Channels.EXECUTION_TO_COORDINATOR, error_msg)
    
    from agents.utils.protocol import Channels
    broker_instance.subscribe(Channels.COORDINATOR_TO_EXECUTION, handle_execution_request)
    
    logger.info("✅ Execution Agent started with RAG integration")
    
    while True:
        await asyncio.sleep(1)

# ============================================================================
# FIXED: Server Initialization
# ============================================================================

async def initialize_execution_agent_for_server(broker_instance):
    """
    Server-compatible initialization for execution agent with RAG system
    FIX: Correct import paths for LocalSandbox
    """
    from dotenv import load_dotenv
    load_dotenv()
    
    if hasattr(broker_instance, '_rag_execution_subscribed'):
        logger.warning("⚠️ RAG Execution agent already subscribed, skipping")
        return
    broker_instance._rag_execution_subscribed = True
    
    try:
        # Import RAG components
        from agents.execution_agent.RAG.code_generation import RAGSystem, RAGConfig
        
        # Initialize RAG system
        try:
            logger.info("🔧 Initializing RAG system...")
            rag_config = RAGConfig(library_name="pywinauto")
            rag_system = RAGSystem(rag_config)
            rag_system.initialize()
            logger.info("✅ RAG system ready")
        except Exception as e:
            logger.error(f"❌ Failed to initialize RAG: {e}")
            logger.info("📦 Starting fallback execution agent...")
            await start_simple_execution_agent(broker_instance)
            return
        
        # FIX: Correct import path for sandbox
        try:
            logger.info("🔧 Initializing LOCAL sandbox pipeline...")
            # Import from the execution notebook/module (code_execution.py or execution.py)
            from agents.execution_agent.RAG.execution import (
                SandboxExecutionPipeline, 
                SandboxConfig,
                ActionCache
                # LocalSandbox  # Make sure this is imported
            )
            
            sandbox_config = SandboxConfig(timeout_seconds=30)
            # Try to enable cache, but continue without it if it fails
            enable_cache = False
            try:
                # Test if ChromaDB is available
                import chromadb
                logger.info( "📦 ChromaDB available - will attempt to enable action cache")
            except ImportError:
                logger.warning("⚠️ ChromaDB not available - disabling action cache")
                enable_cache = False

            # Initialize sandbox with optional cache
            try:
                sandbox_pipeline = SandboxExecutionPipeline(
                    sandbox_config,
                    enable_cache=enable_cache
                )
                
                if hasattr(sandbox_pipeline, 'action_cache') and sandbox_pipeline.action_cache:
                    logger.info(f"✅ Action cache enabled with {sandbox_pipeline.action_cache.collection.count()} cached actions")
                else:
                    logger.info("📝 Running without action cache")
            except Exception as e:
                logger.warning(f"⚠️ Failed to initialize with cache: {e}")
                # Fallback: create without cache
                sandbox_pipeline = SandboxExecutionPipeline(sandbox_config, enable_cache=False)
            
            # Verify LocalSandbox is being used
            if hasattr(sandbox_pipeline, 'local_sandbox'):
                logger.info("✅ Local sandbox pipeline ready")
            else:
                logger.warning("⚠️ Sandbox pipeline created but LocalSandbox not confirmed")
            
        except ImportError as ie:
            logger.error(f"❌ Sandbox import failed: {ie}")
            logger.error(f"   Make sure code_execution.py contains LocalSandbox class")
            logger.info("📦 Starting fallback execution agent...")
            await start_simple_execution_agent(broker_instance)
            return
        except Exception as e:
            logger.error(f"❌ Sandbox initialization error: {e}")
            logger.info("📦 Starting fallback execution agent...")
            await start_simple_execution_agent(broker_instance)
            return
        
        # Start execution agent with RAG
        logger.info("🚀 Starting execution agent with RAG + LocalSandbox...")
        await start_execution_agent_with_rag(broker_instance, rag_system, sandbox_pipeline)
    
    except ImportError as e:
        logger.error(f"❌ Failed to import RAG components: {e}")
        logger.info("📦 Starting fallback execution agent...")
        await start_simple_execution_agent(broker_instance)


async def start_simple_execution_agent(broker_instance):
    """Simple execution agent fallback"""
    from agents.utils.protocol import AgentMessage, MessageType, AgentType, Channels
    
    async def handle_execution_request(message):
        try:
            task_data = message.payload
            task_id = task_data.get('task_id', 'unknown')
            ai_prompt = task_data.get('ai_prompt', '')
            
            logger.info(f"🎯 Fallback execution agent received task {task_id}: {ai_prompt[:50]}...")
            
            result = {
                'task_id': task_id,
                'status': 'pending',
                'content': f"Task '{ai_prompt}' awaiting RAG execution",
                'error': None
            }
            
            response_msg = AgentMessage(
                message_type=MessageType.EXECUTION_RESPONSE,
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
    
    broker_instance.subscribe(Channels.COORDINATOR_TO_EXECUTION, handle_execution_request)
    logger.info("✅ Fallback Execution Agent started")
    
    while True:
        await asyncio.sleep(1)