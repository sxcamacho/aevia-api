from fastapi import APIRouter
from app.models.wish import Wish
from app.services.wish import WishService

router = APIRouter(
    prefix="/wishes",
    tags=["wishes"]
)

@router.post("", status_code=200)
async def create_wish(wish: Wish):
    return await WishService.create_wish(wish) 

@router.post("/{wish_id}/sign", status_code=200)
async def get_signature_payload_for_wish(wish_id: int):
    return await WishService.signature_payload_for_wish(wish_id)