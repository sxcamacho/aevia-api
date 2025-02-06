from fastapi import APIRouter
from app.models.legacy import Legacy
from app.services.legacy import LegacyService

router = APIRouter(
    prefix="/legacies",
    tags=["legacies"]
)

@router.post("", status_code=200)
async def create_legacy(legacy: Legacy):
    return await LegacyService.create_legacy(legacy) 

@router.post("/{legacy_id}/sign", status_code=200)
async def get_signature_message(legacy_id: int):
    return await LegacyService.get_signature_message(legacy_id)