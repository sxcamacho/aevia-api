from fastapi import HTTPException
from app.config.database import supabase
from app.models.legacy import Legacy
from app.services.signature import SignatureService
from app.services.contract import ContractService
from dotenv import load_dotenv
from web3 import Web3
from eth_account.messages import encode_defunct
import os

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
                "first_name": legacy.firstName,
                "last_name": legacy.lastName,
                "email": legacy.email,
                "country": legacy.country or None,
                "trusted_contact_name": legacy.trustedContactName,
                "trusted_contact_email": legacy.trustedContactEmail,
                "email_to": legacy.emailTo or None,
                "email_body": legacy.emailMessage or None,
                "crypto_wallet_from": legacy.cryptoWalletFrom,
                "crypto_wallet_to": legacy.cryptoWalletTo,
                "crypto_token_type": legacy.cryptoTokenType,
                "crypto_token_address": legacy.cryptoTokenAddress,
                "crypto_token_id": legacy.cryptoTokenId,
                "crypto_amount": legacy.cryptoAmount,
                "crypto_signature": None,
                "crypto_chain_id": legacy.cryptoChainId,
                "crypto_contract_address": contract["address"]
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

    @staticmethod
    async def get_last_by_user(user: str):
        try:
            result = supabase.table("legacies").select("*").eq("email", user).order("created_at", desc=True).limit(1).execute()
            return result.data[0]
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error getting last legacy for user {user}: {str(e)}")
        
    @staticmethod
    async def execute_legacy(legacy_id: uuid.UUID):
        try:
            result = supabase.table("legacies").select("*").eq("id", legacy_id).execute()
            data = result.data[0]

            if not data:
                raise HTTPException(status_code=404, detail="Legacy not found")
            
            # Get contract info
            contract = await ContractService.get_contract_by_chain_and_name("AeviaProtocol", data["crypto_chain_id"])
            
            # Initialize web3
            chain_id = data["crypto_chain_id"]
            web3_url = os.getenv(f"WEB3_URL_{chain_id}")
            w3 = Web3(Web3.HTTPProvider(web3_url))
            operator_private_key = os.getenv("OPERATOR_PRIVATE_KEY")
            account = w3.eth.account.from_key(operator_private_key)
            operator_address = account.address
            contract_instance = w3.eth.contract(
                address=contract["address"],
                abi=contract["abi"]
            )

            # Build transaction
            tx = contract_instance.functions.executeLegacy(
                int(data["legacy_id"]),
                data["crypto_token_type"],
                data["crypto_token_address"],
                int(data["crypto_token_id"]) if data["crypto_token_id"] else 0,
                int(data["crypto_amount"]) if data["crypto_amount"] else 0,
                data["crypto_wallet_from"],
                data["crypto_wallet_to"],
                data["crypto_signature"]
            ).build_transaction({
                'from': operator_address,
                'nonce': w3.eth.get_transaction_count(operator_address),
                'gas': 2000000,
                'gasPrice': w3.eth.gas_price
            })

            # Sign and send transaction
            signed_tx = w3.eth.account.sign_transaction(tx, operator_private_key)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            
            # Wait for transaction receipt
            tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
            
            return {
                "legacy": data,
                "transaction": tx_receipt.transactionHash.hex()
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error executing legacy {legacy_id}: {str(e)}")
