from pydantic import BaseModel
from app.enums.token_type import TokenType

class Legacy(BaseModel):
    id: str | None = None
    blokchain_id: str | None = None
    chain_id: int
    token_type: TokenType
    token_address: str
    token_id: str | None = None
    amount: str
    wallet: str
    heir_wallet: str
    signature: str | None = None
    name: str
    telegram_id: str
    telegram_id_emergency: str
    telegram_id_heir: str
    contract_address: str
    signal_confirmation_retries: int | None = None
    signal_requested_at: str | None = None
    signal_received_at: str | None = None
    investment_enabled: bool | None = None
    investment_risk: str | None = None