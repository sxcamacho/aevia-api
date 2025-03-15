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
            # create investment wallet
            wallet = supabase.table("investment_wallets").insert({
                "legacy_id": legacy_id,
            }).execute()

            # get wallet index
            new_index = wallet.data[0]["index"]

            # get wallet from index
            wallet = WalletService.get_wallet_from_index(new_index)

            # update investment wallet
            result = supabase.table("investment_wallets").update({
                "index": new_index,
                "address": wallet.address,
            }).eq("legacy_id", legacy_id).execute()

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