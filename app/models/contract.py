from pydantic import BaseModel
from typing import Any

class Contract(BaseModel):
    chainId: int
    address: str
    name: str
    abi: list[dict[str, Any]]