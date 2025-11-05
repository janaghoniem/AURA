# backend/main.py
from fastapi import FastAPI, Request
from agents.coordinator_agent.coordinator_agent import handle_coordination
from backend.agents.execution_agent.core.exec_agent_main import execute_task

app = FastAPI(title="YUSR Unified Multi-Agent Backend")

@app.get("/")
def root():
    return {"message": "YUSR backend running"}

@app.post("/api/coordinate")
async def coordinate_task(request: Request):
    payload = await request.json()
    return await handle_coordination(payload)

@app.post("/api/execute")
async def execute_task_endpoint(request: Request):
    payload = await request.json()
    return await execute_task(payload)

# Optional health check route for Electron
@app.get("/api/health")
def health():
    return {"status": "ok"}
