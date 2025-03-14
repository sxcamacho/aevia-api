from pydantic import BaseModel
from typing import Any

class InvestmentWallet(BaseModel):
    id: int | None = None
    index: int
    legacy_id: str
    address: str
    created_at: str
    updated_at: str | None = None
    unstaked_at: str | None = None