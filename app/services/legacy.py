from fastapi import HTTPException
from app.config.database import supabase
from app.models.legacy import Legacy
from app.services.signature import SignatureService
import secrets
import os
from dotenv import load_dotenv

load_dotenv()
class LegacyService:
    @staticmethod
    async def create_legacy(legacy: Legacy):
        try:
            # TODO: get based chainId contract
            handler_contract_address = os.getenv("WISH_HANDLER_CONTRACT_ADDRESS")

            result = supabase.table("legacies").insert({
                "legacy_id": secrets.randbelow(2**256),
                "first_name": legacy.firstName or None,
                "last_name": legacy.lastName or None,
                "email": legacy.email or None,
                "country": legacy.country or None,
                "trusted_contact_name": legacy.trustedContactName or None,
                "trusted_contact_email": legacy.trustedContactEmail or None,
                "email_to": legacy.emailTo or None,
                "email_body": legacy.emailMessage or None,
                "crypto_wallet_from": legacy.cryptoWalletFrom or None,
                "crypto_wallet_to": legacy.cryptoWalletTo or None,
                "crypto_token_type": legacy.cryptoTokenType or None,
                "crypto_token_address": legacy.cryptoTokenAddress or None,
                "crypto_token_id": legacy.cryptoTokenId or None,
                "crypto_amount": legacy.cryptoAmount or None,
                "crypto_signature": None,
                "crypto_chain_id": legacy.cryptoChainId or None,
                "crypto_handler_contract_address": handler_contract_address
            }).execute()

            return result.data[0]
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    async def get_signature_payload(legacy_id: int):
        try:
            result = supabase.table("legacies").select("*").eq("id", legacy_id).execute()
            data = result.data[0]

            if not data:
                raise HTTPException(status_code=404, detail="Legacy not found")

            chain_id = data["crypto_chain_id"]
            legacy_handler_address = data["crypto_handler_contract_address"]
            service = SignatureService(legacy_handler_address, chain_id)
            message = service.get_signature_message(
                data["legacy_id"],
                data["crypto_token_type"],
                data["crypto_token_address"],
                data["crypto_token_id"],
                data["crypto_amount"],
                data["crypto_wallet_from"],
                data["crypto_wallet_to"]
            )
            return message
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
