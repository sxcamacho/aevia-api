from fastapi import HTTPException
from app.config.database import supabase
from app.models.wish import Wish
from app.services.signature import SignatureService
import secrets
import os
from dotenv import load_dotenv

load_dotenv()
class WishService:
    @staticmethod
    async def create_wish(wish: Wish):
        try:
            key_hash = secrets.randbelow(2**256)
            # TODO: get based chainId contract
            handler_contract_address = os.getenv("WISH_HANDLER_CONTRACT_ADDRESS")
            result = supabase.table("wishes").insert({
                "key_hash": str(key_hash),
                "first_name": wish.firstName or None,
                "last_name": wish.lastName or None,
                "email": wish.email or None,
                "country": wish.country or None,
                "trusted_contact_name": wish.trustedContactName or None,
                "trusted_contact_email": wish.trustedContactEmail or None,
                "email_to": wish.emailTo or None,
                "email_body": wish.emailMessage or None,
                "crypto_wallet_from": wish.cryptoWalletFrom or None,
                "crypto_wallet_to": wish.cryptoWalletTo or None,
                "crypto_token_type": wish.cryptoTokenType or None,
                "crypto_token_address": wish.cryptoTokenAddress or None,
                "crypto_token_id": wish.cryptoTokenId or None,
                "crypto_amount": wish.cryptoAmount or None,
                "crypto_signature": None,
                "crypto_chain_id": wish.cryptoChainId or None,
                "crypto_handler_contract_address": handler_contract_address
            }).execute()

            return result.data[0]
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    async def signature_payload_for_wish(wish_id: int):
        try:
            result = supabase.table("wishes").select("*").eq("id", wish_id).execute()
            wish_data = result.data[0]

            if not wish_data:
                raise HTTPException(status_code=404, detail="Wish not found")

            chain_id = wish_data["crypto_chain_id"]
            wish_handler_address = wish_data["crypto_handler_contract_address"]
            service = SignatureService(wish_handler_address, chain_id)
            typed_data = service.get_typed_data(
                wish_data["key_hash"],
                wish_data["crypto_token_type"],
                wish_data["crypto_token_address"],
                wish_data["crypto_token_id"],
                wish_data["crypto_amount"],
                wish_data["crypto_wallet_from"],
                wish_data["crypto_wallet_to"]
            )
            
            message = service.get_signing_message(typed_data)
            return message
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
