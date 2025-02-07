from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx
from typing import Optional

router = APIRouter(
    prefix="/protocol",
    tags=["protocol"]
)

class ProtocolRequest(BaseModel):
    user: str
    beneficiary: str
    legacy: str
    contact_id: str

@router.post("/start_cron")
async def start_cron(request: ProtocolRequest):
    try:
        await call_agent_api("user", request.user, request.beneficiary, request.legacy, request.contact_id)
        return {"status": "success", "message": "Cron started successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/alive")
async def handle_alive_protocol(request: ProtocolRequest):
    try:
        return {
            "status": "success",
            "message": f"Alive protocol executed for user {request.user}",
            "protocol": "alive"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/emergency")
async def handle_emergency_protocol(request: ProtocolRequest):
    try:
        await call_agent_api("emergency", request.user, request.beneficiary, request.legacy, request.contact_id)
        return {"status": "success", "message": "Emergency protocol initiated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/dead")
async def handle_dead_protocol(request: ProtocolRequest):
    try:
        await call_agent_api("beneficiary", request.user, request.beneficiary, request.legacy, request.contact_id)
        return {
            "status": "success",
            "message": f"Dead protocol executed for user {request.user}",
            "protocol": "dead"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def call_agent_api(status_agent: str, user: str, beneficiary: str, legacy: str, contact_id: str):
    async with httpx.AsyncClient() as client:
        data = {
            "user": user,
            "beneficiary": beneficiary,
            "legacy": legacy,
            "contact_id": contact_id,
            "status_agent": status_agent
        }
        try:
            response = await client.post(
                f"http://localhost:8000/start_conversation_{status_agent}/",
                json=data,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error connecting to service: {str(e)}"
            )
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Internal service error: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Unexpected error: {str(e)}"
            ) 