from pydantic import BaseModel
from typing import Any

class InvestmentWallet(BaseModel):
    legacy_id: int
    name: str
    abi: list[dict[str, Any]]