import httpx
from typing import Dict, Any

async def send_request(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)
        return response.json()
