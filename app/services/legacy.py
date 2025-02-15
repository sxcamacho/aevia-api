from fastapi import HTTPException
from app.config.database import supabase
from app.models.legacy import Legacy
from app.services.signature import SignatureService
from app.services.contract import ContractService
from dotenv import load_dotenv
from web3 import Web3
import os
import asyncio
import json
import httpx


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
            chain_id = data["crypto_chain_id"]
            contract = await ContractService.get_contract_by_chain_and_name("AeviaProtocol", chain_id)
            contract_name = contract["name"]
            print(f"interact with {contract_name} contract")
            # Initialize web3
            web3_url = os.getenv(f"WEB3_URL_{chain_id}")
            print(f"connecting to {web3_url}")
            w3 = Web3(Web3.HTTPProvider(web3_url))
            operator_private_key = os.getenv("OPERATOR_PRIVATE_KEY")
            account = w3.eth.account.from_key(operator_private_key)
            operator_address = account.address
            contract_instance = w3.eth.contract(
                address=contract["address"],
                abi=contract["abi"]
            )

            # Convert parameters to correct types
            params = LegacyService._convert_legacy_params(data)

            # Configure gas based on chain
            if int(chain_id) == 5003:  # Mantle
                gas_price = w3.eth.gas_price    
                gas_limit = 300000000
            else:
                gas_price = w3.eth.gas_price
                gas_limit = 2000000

            # Build transaction
            tx = contract_instance.functions.executeLegacy(
                params["legacy_id"],
                params["token_type"],
                params["token_address"],
                params["token_id"],
                params["amount"],
                params["wallet_from"],
                params["wallet_to"],
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
            raise HTTPException(status_code=500, detail=f"Error executing legacy {legacy_id}: {str(e)}")

    @staticmethod
    def _convert_legacy_params(data):
        """Helper method to convert legacy data to correct types"""
        return {
            "legacy_id": int(data["legacy_id"]),
            "token_type": int(data["crypto_token_type"]),
            "token_address": str(data["crypto_token_address"]),
            "token_id": int(data["crypto_token_id"]) if data["crypto_token_id"] else 0,
            "amount": int(data["crypto_amount"]) if data["crypto_amount"] else 0,
            "wallet_from": str(data["crypto_wallet_from"]),
            "wallet_to": str(data["crypto_wallet_to"]),
            "signature": str(data["crypto_signature"])
        }
    
    @staticmethod
    async def stake(legacy_id: uuid.UUID):
        try:
            # SEED_PHRASE = os.getenv("WALLET_MNEMONIC_PHRASE")
            STAKEKIT_API_KEY = os.getenv("STAKEKIT_API_KEY")
            STAKEKIT_BASE_URL = os.getenv("STAKEKIT_BASE_URL")

            w3 = Web3()
            # wallet = w3.eth.account.from_mnemonic(SEED_PHRASE)
            operator_private_key = os.getenv("OPERATOR_PRIVATE_KEY")
            wallet = w3.eth.account.from_key(operator_private_key)

            result = supabase.table("legacies").select("*").eq("id", legacy_id).execute()
            data = result.data[0]
            
            if not data:
                raise HTTPException(status_code=404, detail="Legacy not found")
            
            timeouts = httpx.Timeout(
                connect=10.0,
                read=300.0,
                write=60.0,
                pool=10.0
            )
            async with httpx.AsyncClient(timeout=timeouts) as session:
                
                try:
                    response = await session.post(
                        f"{STAKEKIT_BASE_URL}/actions/enter",
                        headers={"Content-Type": "application/json", "X-API-KEY": STAKEKIT_API_KEY},
                        json={
                            "integrationId": "ethereum-matic-native-staking",
                            "addresses": {"address": wallet.address},
                            "args": {"amount": "1", "validatorAddress": "0x857679d69fe50e7b722f94acd2629d80c355163d" },
                        },
                    )
                    # ethereum-matic-native-staking
                    # avalanche-avax-native-staking
                    stake_session_response = response.json()
                except httpx.RequestError as e:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Error connecting with staking provider"
                    )
                except httpx.HTTPStatusError as e:
                    raise HTTPException(
                        status_code=e.response.status_code,
                        detail=f"Internal service error: {str(e)}"
                    )
                
                for i, partial_tx in enumerate(stake_session_response["transactions"]):
                    if partial_tx["status"] == "SKIPPED":
                        continue

                    print(
                        f"Action {i + 1} out of {len(stake_session_response['transactions'])} {partial_tx['type']}"
                    )

                    # get gas
                    try:
                        response = await session.get(
                            f"{STAKEKIT_BASE_URL}/transactions/gas/ethereum",
                            headers={"Accept": "application/json", "X-API-KEY": STAKEKIT_API_KEY},
                        )
                        gas_response = response.json()
                    except httpx.RequestError as e:
                        raise HTTPException(
                            status_code=500,
                            detail=f"Error getting gas for staking: {str(e)}"
                        )
                    except httpx.HTTPStatusError as e:
                        raise HTTPException(
                            status_code=e.response.status_code,
                            detail=f"Internal service error: {str(e)}"
                        )

                    # build transaction
                    try:
                        response = await session.patch(
                            f"{STAKEKIT_BASE_URL}/transactions/{partial_tx['id']}",
                            headers={"Accept": "application/json", "X-API-KEY": STAKEKIT_API_KEY},
                            json={"gasArgs": gas_response["modes"]["values"][1]["gasArgs"]},
                        )
                        constructed_transaction_response = response.json()
                    except httpx.RequestError as e:
                        raise HTTPException(
                            status_code=500,
                            detail=f"Error constructing staking transaction: {str(e)}"
                        )
                    except httpx.HTTPStatusError as e:
                        raise HTTPException(
                            status_code=e.response.status_code,
                            detail=f"Internal service error: {str(e)}"
                        )

                    try:
                        unsigned_transaction = constructed_transaction_response["unsignedTransaction"]
                        unsigned_data = json.loads(unsigned_transaction)
                        transaction_data = {
                            "from": Web3.to_checksum_address(unsigned_data["from"]),
                            "gas": int(unsigned_data["gasLimit"], 16),
                            "to": Web3.to_checksum_address(unsigned_data["to"]),
                            "data": unsigned_data["data"],
                            "nonce": unsigned_data["nonce"],
                            "type": unsigned_data["type"],
                            "maxFeePerGas": int(unsigned_data["maxFeePerGas"], 16),
                            "maxPriorityFeePerGas": int(unsigned_data["maxPriorityFeePerGas"], 16),
                            "chainId": unsigned_data["chainId"]
                        }
                        signed_tx = w3.eth.account.sign_transaction(transaction_data, wallet.key)
                    except json.JSONDecodeError as e:
                        raise HTTPException(
                            status_code=500,
                            detail=f"Error parsing transaction JSON: {str(e)}"
                        )

                    # send signed transaction
                    try:
                        signed_tx_hex = "0x" + signed_tx.raw_transaction.hex()
                        await session.post(
                            f"{STAKEKIT_BASE_URL}/transactions/{partial_tx['id']}/submit",
                            headers={"Accept": "application/json", "X-API-KEY": STAKEKIT_API_KEY},
                            json={"signedTransaction": signed_tx_hex},
                        )
                    except httpx.RequestError as e:
                        raise HTTPException(
                            status_code=500,
                            detail=f"Error sending transaction: {str(e)}"
                        )
                    except httpx.HTTPStatusError as e:
                        raise HTTPException(
                            status_code=e.response.status_code,
                            detail=f"Internal service error: {str(e)}"
                        )

                    # verify transaction status
                    while True:
                        try:
                            response = await session.get(
                                f"{STAKEKIT_BASE_URL}/transactions/{partial_tx['id']}/status",
                                headers={"Accept": "application/json", "X-API-KEY": STAKEKIT_API_KEY},
                            )
                            status_response = response.json()
                        except httpx.RequestError as e:
                            raise HTTPException(
                                status_code=500,
                                detail=f"Error getting transaction status: {str(e)}"
                            )
                        except httpx.HTTPStatusError as e:
                            raise HTTPException(
                                status_code=e.response.status_code,
                                detail=f"Internal service error: {str(e)}"
                            )
                        
                        status = status_response["status"]
                        if status == "CONFIRMED":
                            print(status_response["url"])
                            break
                        elif status == "FAILED":
                            print("TRANSACTION FAILED")
                            break
                        else:
                            print("Pending...")
                            await asyncio.sleep(1)

            return {
                "status": "staked successfully",
                "transaction_url": status_response["url"]
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error staking legacy {legacy_id}: {str(e.with_traceback())}")
            
            
