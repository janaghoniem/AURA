"""
Execution Agent FastAPI Server
Receives tasks from Coordinator and executes them via ExecutionAgent
"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from exec_agent_main import ExecutionAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="YUSR Execution Agent",
    description="UI automation and system command execution",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Execution Agent
execution_agent = ExecutionAgent()

@app.post("/execute")
async def execute_task(request: Request):
    """
    Execute a task from Coordinator Agent
    
    Expected JSON format:
    {
        "task_id": "uuid",
        "action": "open_app",
        "context": "local",
        "params": {
            "action_type": "open_app",
            "app_name": "Calculator"
        },
        "priority": "normal",
        "timeout": 30,
        "retry_count": 3
    }
    """
    try:
        task = await request.json()
        logger.info(f"Received task: {task.get('task_id')} - {task.get('action')}")
        
        # Validate required fields
        if not task.get("action"):
            raise HTTPException(status_code=400, detail="Missing 'action' field")
        if not task.get("context"):
            raise HTTPException(status_code=400, detail="Missing 'context' field")
        if not task.get("params"):
            raise HTTPException(status_code=400, detail="Missing 'params' field")
        
        # Execute task using ExecutionAgent
        result = execution_agent.execute_from_dict(task)
        
        logger.info(f"Task {task.get('task_id')} completed: {result.get('status')}")
        
        return JSONResponse(
            status_code=200,
            content={
                "task_id": task.get("task_id"),
                "status": result.get("status", "unknown"),
                "details": result.get("details", ""),
                "metadata": result.get("metadata", {}),
                "error": result.get("error")
            }
        )
    
    except HTTPException as he:
        raise he
    
    except Exception as e:
        logger.error(f"Execution error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Execution failed: {str(e)}"
        )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "YUSR Execution Agent",
        "version": "2.0.0"
    }

@app.get("/")
async def root():
    """Root endpoint with API documentation"""
    return {
        "service": "YUSR Execution Agent",
        "description": "UI automation and system command execution",
        "endpoints": {
            "/execute": "POST - Execute task from Coordinator",
            "/health": "GET - Service health check",
            "/": "GET - API documentation"
        },
        "supported_contexts": ["local", "web", "system"],
        "example_task": {
            "task_id": "uuid-123",
            "action": "open_calculator",
            "context": "local",
            "params": {
                "action_type": "open_app",
                "app_name": "Calculator"
            }
        }
    }

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Execution Agent on 0.0.0.0:8001")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level="info"
    )