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