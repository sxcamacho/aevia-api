from fastapi import HTTPException
from app.config.database import supabase
from app.models.wish import Wish

class WishService:
    @staticmethod
    async def create_wish(wish: Wish):
        try:
            result = supabase.table("wishes").insert({
                "first_name": wish.firstName,
                "last_name": wish.lastName,
                "email": wish.email,
                "country": wish.country,
                "trusted_contact_name": wish.trustedContactName,
                "trusted_contact_email": wish.trustedContactEmail,
                "email_to": wish.emailTo,
                "email_body": wish.emailMessage,
                "crypto_wallet_to": wish.cryptoWalletTo,
                "crypto_token_address": wish.cryptoTokenAddress,
                "crypto_amount": wish.cryptoAmount,
                "crypto_signature": "0x",
            }).execute()

            return result.data[0]
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) 
