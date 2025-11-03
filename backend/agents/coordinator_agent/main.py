from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from coordinator_agent import coordinator_graph
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="YUSR Coordinator Agent",
    description="Multi-agent orchestration for accessibility automation",
    version="2.0.0"
)

@app.post("/coordinate")
async def coordinate_task(request: Request):
    """
    Main endpoint for task coordination.
    
    Accepts JSON from Language Agent and orchestrates execution across:
    - Execution Agent (local/web/system automation)
    - Reasoning Agent (analysis, summarization, content generation)
    
    Returns:
    - Execution results on success
    - Clarification question if input is ambiguous
    - Error details on failure
    """
    try:
        payload = await request.json()
        logger.info(f"Received task: {payload.get('action', 'unknown')}")
        
        # Validate basic structure
        if not payload.get("action"):
            raise HTTPException(
                status_code=400,
                detail="Missing required field: 'action'"
            )
        
        if not payload.get("context"):
            raise HTTPException(
                status_code=400,
                detail="Missing required field: 'context'"
            )
        
        # Execute coordination graph
        final_state = await coordinator_graph.ainvoke({"input": payload})
        
        # Handle clarification requests
        if final_state.get("clarification"):
            logger.info(f"Clarification needed: {final_state['clarification']}")
            return JSONResponse(
                status_code=200,
                content={
                    "status": "needs_clarification",
                    "question": final_state["clarification"]
                }
            )
        
        # Return successful execution results
        logger.info(f"Task completed: {final_state.get('status')}")
        return JSONResponse(
            status_code=200,
            content={
                "status": final_state.get("status", "completed"),
                "results": final_state.get("results", {}),
                "task_id": payload.get("task_id", "unknown")
            }
        )
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON payload")
        raise HTTPException(status_code=400, detail="Invalid JSON format")
    
    except Exception as e:
        logger.error(f"Coordination error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Coordination failed: {str(e)}"
        )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "YUSR Coordinator Agent",
        "version": "2.0.0"
    }

@app.get("/")
async def root():
    """Root endpoint with API documentation"""
    return {
        "service": "YUSR Coordinator Agent",
        "description": "Multi-agent task orchestration for accessibility",
        "endpoints": {
            "/coordinate": "POST - Submit task for coordination",
            "/health": "GET - Service health check",
            "/": "GET - API documentation"
        },
        "usage": {
            "method": "POST /coordinate",
            "body": {
                "action": "send_message",
                "context": "local",
                "params": {
                    "action_type": "send_message",
                    "platform": "discord",
                    "message": "Hello!"
                }
            }
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)