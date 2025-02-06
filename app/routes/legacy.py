from fastapi import APIRouter, Body
from app.models.legacy import Legacy
from app.services.legacy import LegacyService
import uuid
router = APIRouter(
    prefix="/legacies",
    tags=["legacies"]
)

@router.post("", status_code=200)
async def create_legacy(legacy: Legacy):
    return await LegacyService.create_legacy(legacy) 

@router.post("/{id}/sign", status_code=200)
async def get_signature_message(id: uuid.UUID):
    return await LegacyService.get_signature_message(id)

@router.patch("/{id}/sign", status_code=200)
async def set_signature_for_legacy(id: uuid.UUID, body: dict = Body(...)):
    return await LegacyService.set_signature(id, body["signature"]) 
