from fastapi import HTTPException
from app.config.database import supabase
from app.models.legacy import Legacy
# from app.models.investment_wallet import InvestmentWallet
from app.services.signature import SignatureService
from app.services.contract import ContractService
from dotenv import load_dotenv
from web3 import Web3
import os
# import httpx
# from app.enums.chain import Chain
# from app.enums.token import Token
from app.enums.token_type import TokenType
from app.services.stakekit import StakeKitService
# from app.services.wallet import WalletService
from app.services.investment_wallet import InvestmentWalletService
# from datetime import datetime, timedelta, timezone
import secrets
import uuid

load_dotenv()

class LegacyService:
    @staticmethod
    async def create_legacy(legacy: Legacy):
        try:
            print(f"create legacy {legacy.name}")
            contract = await ContractService.get_contract_by_chain_and_name("AeviaProtocol", legacy.chain_id)
            result = supabase.table("legacies").insert({
                "blockchain_id": secrets.randbelow(2**256),
                "chain_id": legacy.chain_id,
                "token_type": legacy.token_type,
                "token_address": legacy.token_address,
                "token_id": legacy.token_type == TokenType.ERC721 and legacy.token_id or None,
                "amount": legacy.amount,
                "wallet": legacy.wallet,
                "heir_wallet": legacy.heir_wallet,
                "signature": None,
                "name": legacy.name,
                "telegram_id": legacy.telegram_id,
                "telegram_id_emergency": legacy.telegram_id_emergency,
                "telegram_id_heir": legacy.telegram_id_heir,
                "contract_address": contract.address,   
                "signal_confirmation_retries": legacy.signal_confirmation_retries,
                "signal_requested_at": legacy.signal_requested_at,
                "signal_received_at": legacy.signal_received_at,
                "investment_enabled": legacy.investment_enabled,
                "investment_risk": legacy.investment_risk,
            }).execute()
            legacy = Legacy(**result.data[0])

            if legacy.investment_enabled:
                investment_wallet = await InvestmentWalletService.create_investment_wallet(legacy.id)
                legacy.investment_wallet = investment_wallet.address
            
            return legacy
        except Exception as e:
            raise HTTPException(
                    status_code=500,
                    detail=f"Error creacting legacy: {str(e)}"
                )

    @staticmethod
    async def get_legacy(legacy_id: uuid.UUID):
        try:
            result = supabase.table("legacies").select("*").eq("id", legacy_id).execute()
            return Legacy(**result.data[0])
        except Exception as e:
            raise HTTPException(
                    status_code=500,
                    detail=f"Error getting legacy: {str(e)}"
                )

    @staticmethod
    async def get_signature_message(id: uuid.UUID):
        try:
            result = supabase.table("legacies").select("*").eq("id", id).execute()
            if not result.data:
                raise HTTPException(status_code=404, detail="Legacy not found")
            
            legacy = Legacy(**result.data[0])

            service = SignatureService(legacy.contract_address, legacy.chain_id)
            message = service.get_signature_message(
                legacy.blockchain_id,
                legacy.token_type,
                legacy.token_address,
                legacy.token_id,
                legacy.amount,
                legacy.wallet,
                legacy.heir_wallet
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
            if not result.data:
                raise HTTPException(status_code=404, detail="Legacy not found")
                

            result = supabase.table("legacies").update({
                "signature": signature
            }).eq("id", id).execute()

            return Legacy(**result.data[0])
        except Exception as e:
            raise HTTPException(
                    status_code=500,
                    detail=f"Error setting signature: {str(e)}"
                )

    @staticmethod
    async def get_last_by_user(user: str):
        try:
            result = supabase.table("legacies").select("*").eq("telegram_id", user).order("created_at", desc=True).limit(1).execute()
            if not result.data:
                raise HTTPException(status_code=404, detail="No legacy found for user")
            
            return Legacy(**result.data[0])
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error getting last legacy for user {user}: {str(e)}")
        

    @staticmethod
    async def execute_legacy(legacy_id: uuid.UUID):
        try:
            legacy = await LegacyService.get_legacy(legacy_id)
            if legacy.investment_enabled:
                result = await LegacyService.execute_legacy_investment(legacy)
            else:
                result = await LegacyService.execute_legacy_standard(legacy)

            return result
            
        except HTTPException as e:
            raise e
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error executing legacy {legacy_id}: {str(e)}")        
            

    @staticmethod
    async def execute_legacy_standard(legacy: Legacy):
        try:
            
            web3_url = os.getenv(f"WEB3_URL_{legacy.chain_id}")
            
            # Get contract info
            contract = await ContractService.get_contract_by_chain_and_name("AeviaProtocol", legacy.chain_id)
            print(f"interact with {contract.name} contract")
            
            # Initialize web3
            print(f"connecting to {web3_url}")
            w3 = Web3(Web3.HTTPProvider(web3_url))
            
            operator_private_key = os.getenv("OPERATOR_PRIVATE_KEY")
            account = w3.eth.account.from_key(operator_private_key)
            operator_address = account.address
            
            contract_instance = w3.eth.contract(
                address=contract.address,
                abi=contract.abi
            )

            # Build transaction
            tx = contract_instance.functions.executeLegacy(
                int(legacy.blockchain_id),
                legacy.token_type.value,
                legacy.token_address,
                int(legacy.token_id if legacy.token_id else 0),
                int(legacy.amount),
                legacy.wallet,
                legacy.heir_wallet,
                legacy.signature
            ).build_transaction({
                "from": operator_address,
                "nonce": w3.eth.get_transaction_count(operator_address),
                "gas": 2000000,
                "gasPrice": w3.eth.gas_price
            })

            # Sign and send transaction
            signed_tx = w3.eth.account.sign_transaction(tx, operator_private_key)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            
            # Wait for transaction receipt
            tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
            
            return {
                "legacy": legacy,
                "transaction": tx_receipt.transactionHash.hex()
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error executing legacy {legacy.blockchain_id}: {str(e)}")
    
    @staticmethod
    async def get_balance(legacy_id: uuid.UUID):
        legacy = await LegacyService.get_legacy(legacy_id)
        if not legacy:
            raise HTTPException(status_code=404, detail="Legacy not found")
        if not legacy.investment_enabled:
            raise HTTPException(status_code=400, detail="Legacy is not investment enabled")
        
        balances = await StakeKitService.get_stake_balance(legacy)
        return StakeKitService.format_balance_data(balances)

    @staticmethod
    async def execute_legacy_investment(legacy: Legacy):
        response = await StakeKitService.perform_staking_action(legacy, "exit")
        await InvestmentWalletService.update_staked_at(legacy.id)
        return response
            
    @staticmethod
    async def stake(legacy_id: uuid.UUID):
        legacy = await LegacyService.get_legacy(legacy_id)
        if not legacy:
            raise HTTPException(status_code=404, detail="Legacy not found")
        return await StakeKitService.perform_staking_action(legacy, "enter")

    @staticmethod
    async def claim(legacy_id: uuid.UUID):
        legacy = await LegacyService.get_legacy(legacy_id)
        if not legacy:
            raise HTTPException(status_code=404, detail="Legacy not found")
        return await StakeKitService.claim(legacy)

    @staticmethod
    async def withdraw(legacy_id: uuid.UUID):
        legacy = await LegacyService.get_legacy(legacy_id)
        if not legacy:
            raise HTTPException(status_code=404, detail="Legacy not found")
        return await StakeKitService.withdraw(legacy)