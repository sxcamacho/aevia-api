from fastapi import HTTPException
from app.config.database import supabase
from app.models.legacy import Legacy
from app.models.investment_wallet import InvestmentWallet
from app.services.signature import SignatureService
from app.services.contract import ContractService
from dotenv import load_dotenv
from web3 import Web3
import os
import httpx
from app.enums.chain import Chain
from app.enums.token import Token
from app.enums.token_type import TokenType
from app.services.stakekit import StakeKitService
from app.services.wallet import WalletService
from app.services.investment_wallet import InvestmentWalletService
from datetime import datetime, timedelta, timezone
import secrets
import uuid

load_dotenv()

class LegacyService:
    @staticmethod
    async def create_legacy(legacy: Legacy):
        try:
            contract = await ContractService.get_contract_by_chain_and_name("AeviaProtocol", legacy.chain_id)
            result = supabase.table("legaciesV2").insert({
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
            result = supabase.table("legaciesV2").select("*").eq("id", legacy_id).execute()
            return Legacy(**result.data[0])
        except Exception as e:
            raise HTTPException(
                    status_code=500,
                    detail=f"Error getting legacy: {str(e)}"
                )

    @staticmethod
    async def get_signature_message(id: uuid.UUID):
        try:
            result = supabase.table("legaciesV2").select("*").eq("id", id).execute()
            if not result.data:
                raise HTTPException(status_code=404, detail="Legacy not found")
            
            legacy = Legacy(**result.data[0])

            service = SignatureService(legacy.contract_address, legacy.chain_id)
            message = service.get_signature_message(
                legacy.id,
                legacy.token_type,
                legacy.token_address,
                legacy.token_id,
                legacy.amount,
                legacy.wallet,
                legacy.wallet_heir
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
            result = supabase.table("legaciesV2").select("*").eq("id", id).execute()
            if not result.data:
                raise HTTPException(status_code=404, detail="Legacy not found")
                

            result = supabase.table("legaciesV2").update({
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
            result = supabase.table("legaciesV2").select("*").eq("email", user).order("created_at", desc=True).limit(1).execute()
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
            
            # TODO: use mnemonic
            operator_private_key = os.getenv("OPERATOR_PRIVATE_KEY")
            account = w3.eth.account.from_key(operator_private_key)
            operator_address = account.address
            
            contract_instance = w3.eth.contract(
                address=contract["address"],
                abi=contract["abi"]
            )

            # Convert parameters to correct types
            params = LegacyService._convert_legacy_params(legacy)

            # Configure gas based on chain
            if int(legacy.chain_id) in [5000, 5003]:  # Mantle (mainnet y testnet)
                gas_price = w3.eth.gas_price    
                gas_limit = 300000000
            else:
                gas_price = w3.eth.gas_price
                gas_limit = 2000000

            # Build transaction
            tx = contract_instance.functions.executeLegacy(
                params["blockchain_id"],
                params["token_type"],
                params["token_address"],
                params["token_id"],
                params["amount"],
                params["wallet"],
                params["heir_wallet"],
                params["signature"]
            ).build_transaction({
                "from": operator_address,
                "nonce": w3.eth.get_transaction_count(operator_address),
                "gas": gas_limit,
                "gasPrice": gas_price
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
            raise HTTPException(status_code=500, detail=f"Error executing legacy {blockchain_id}: {str(e)}")

    @staticmethod
    def _convert_legacy_params(legacy: Legacy):
        """Helper method to convert legacy data to correct types"""
        return {
            "blockchain_id": int(legacy.blockchain_id),
            "token_type": int(legacy.token_type),
            "token_address": str(legacy.token_address),
            "token_id": int(legacy.token_id) if legacy.token_id else 0,
            "amount": int(legacy.amount) if legacy.amount else 0,
            "wallet": str(legacy.wallet),
            "heir_wallet": str(legacy.heir_wallet),
            "signature": str(legacy.signature)
        }
    
    @staticmethod
    async def execute_legacy_investment(legacy: Legacy):
        response = await StakeKitService.perform_staking_action(legacy, "exit", "unstak")
        await InvestmentWalletService.update_staked_at(legacy.id)
        return response
            
    @staticmethod
    async def stake(legacy_id: uuid.UUID):
        legacy = await LegacyService.get_legacy(legacy_id)
        if not legacy:
            raise HTTPException(status_code=404, detail="Legacy not found")
        return await StakeKitService.perform_staking_action(legacy, "enter", "stak")

    @staticmethod
    async def withdraw(legacy_id: uuid.UUID):
        legacy = await LegacyService.get_legacy(legacy_id)
        if not legacy:
            raise HTTPException(status_code=404, detail="Legacy not found")
        investment_wallet = await InvestmentWalletService.get_investment_wallet(legacy.id)
        if not investment_wallet.unstaked_at:
            raise HTTPException(status_code=404, detail="Unstaked_at not found")

        unstaked_at_datetime = datetime.fromisoformat(investment_wallet.unstaked_at)
        if unstaked_at_datetime <= datetime.now(timezone.utc) - timedelta(days=2):
            return await StakeKitService.get_stake_balance(legacy)
        else:
            return await StakeKitService.get_stake_balance(legacy)
            #raise HTTPException(status_code=404, detail="The 2-day period has not passed yet")
        
