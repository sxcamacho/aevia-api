from fastapi import HTTPException
from app.config.database import supabase
from app.models.legacy import Legacy
from app.services.signature import SignatureService
from app.services.contract import ContractService
from dotenv import load_dotenv

import secrets
import uuid

load_dotenv()
class LegacyService:
    @staticmethod
    async def create_legacy(legacy: Legacy):
        try:
            # TODO: get based chainId contract
            contract = await ContractService.get_contract_by_chain_and_name("AeviaProtocol", legacy.cryptoChainId)

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
                "crypto_contract_address": contract.address
            }).execute()

            return result.data[0]
        except Exception as e:
            raise HTTPException(
                    status_code=500,
                    detail=f"Error creacting legacy: {str(e)}"
                )

    @staticmethod
    async def get_signature_message(id: uuid.UUID):
        try:
            result = supabase.table("legacies").select("*").eq("id", id).execute()
            data = result.data[0]

            if not data:
                raise HTTPException(status_code=404, detail="Legacy not found")

            chain_id = data["crypto_chain_id"]
            contract_address = data["crypto_contract_address"]
            service = SignatureService(contract_address, chain_id)
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
            raise HTTPException(
                    status_code=500,
                    detail=f"Error getting signature message: {str(e)}"
                )

    @staticmethod
    async def set_signature(id: uuid.UUID, signature: str):
        try:
            result = supabase.table("legacies").select("*").eq("id", id).execute()
            data = result.data[0]

            if not data:
                raise HTTPException(status_code=404, detail="Legacy not found")

            result = supabase.table("legacies").update({
                "crypto_signature": signature
            }).eq("id", id).execute()

            return result.data[0]
        except Exception as e:
            raise HTTPException(
                    status_code=500,
                    detail=f"Error setting signature: {str(e)}"
                )
