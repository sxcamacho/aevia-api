from fastapi import HTTPException
from app.config.database import supabase
from app.models.investment_wallet import InvestmentWallet
from dotenv import load_dotenv
import httpx
from datetime import datetime, timezone
from app.services.wallet import WalletService

import secrets
import uuid

timeouts = httpx.Timeout(
    connect=10.0,
    read=300.0,
    write=60.0,
    pool=10.0
)

load_dotenv()

class InvestmentWalletService:
    @staticmethod
    async def create_investment_wallet(legacy_id: uuid.UUID):
        try:
            result = supabase.table("investment_wallets").select("index").order("index", desc=True).limit(1).execute()
            new_index = result.data[0]["index"] + 1 if result.data else 0
            wallet = WalletService.get_wallet_from_index(new_index)

            result = supabase.table("investment_wallets").insert({
                "index": new_index,
                "legacy_id": legacy_id,
                "address": wallet.address,
            }).execute()

            return InvestmentWallet(**result.data[0])
        except Exception as e:
            raise HTTPException(
                    status_code=500,
                    detail=f"Error creacting investment wallet: {str(e)}"
                )
    
    @staticmethod
    async def get_investment_wallet(legacy_id: uuid.UUID):
        try:
            result = supabase.table("investment_wallets").select("*").eq("legacy_id", legacy_id).execute()
            return InvestmentWallet(**result.data[0])
        except Exception as e:
            raise HTTPException(
                    status_code=500,
                    detail=f"Error getting investment wallet: {str(e)}"
                )
    
    @staticmethod
    async def update_staked_at(legacy_id: uuid.UUID):
        try:
            result = supabase.table("investment_wallets").update({"unstaked_at": datetime.now(timezone.utc).isoformat()}).eq("legacy_id", legacy_id).execute()
            return InvestmentWallet(**result.data[0])
        except Exception as e:
            raise HTTPException(
                    status_code=500,
                    detail=f"Error getting investment wallet: {str(e)}"
                )