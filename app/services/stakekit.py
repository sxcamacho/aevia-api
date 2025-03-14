import os
import httpx
from fastapi import HTTPException
from dotenv import load_dotenv
from app.enums.chain import Chain
from app.enums.token import Token
from web3 import Web3
import asyncio
import json
from app.models.legacy import Legacy
from app.services.investment_wallet import InvestmentWalletService
from app.services.wallet import WalletService
import uuid

timeouts = httpx.Timeout(
    connect=10.0,
    read=300.0,
    write=60.0,
    pool=10.0
)

load_dotenv()

class StakeKitService:
    API_KEY = os.getenv("STAKEKIT_API_KEY")
    BASE_URL = os.getenv("STAKEKIT_BASE_URL")
    
    if not API_KEY:
        raise ValueError("STAKEKIT_API_KEY environment variable is not set")
    if not BASE_URL:
        raise ValueError("STAKEKIT_BASE_URL environment variable is not set")
    
    TIMEOUTS = httpx.Timeout(
        connect=10.0,
        read=300.0,
        write=60.0,
        pool=10.0
    )


    @staticmethod
    async def get_yield_info(integration_id: str):
        """Get yield information for a specific integration from StakeKit"""
        try:
            async with httpx.AsyncClient(timeout=StakeKitService.TIMEOUTS) as session:
                response = await session.get(
                    f"{StakeKitService.BASE_URL}/yields/{integration_id}",
                    headers={
                        "Accept": "application/json",
                        "X-API-KEY": StakeKitService.API_KEY
                    }
                )
                
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Error getting yield information: {response.text}"
                    )
                    
                return response.json()
                
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error connecting with staking provider: {str(e)}"
            )

    @staticmethod
    def get_stakekit_integration_id(chain_id: int, token_address: str):
        if chain_id == Chain.EthereumMainnet and token_address == Token.ETHEREUM_POL.value:
            return {
                "id": "ethereum-matic-native-staking",
                # "validatorAddress": "0x857679d69fe50e7b722f94acd2629d80c355163d",
                # "minAmount": 1
            }
        elif chain_id == Chain.AvalancheMainnet and token_address == Token.AVALANCHE_AVAX.value:
            return {
                "id": "avalanche-avax-native-staking",
                # "validatorAddress": "NodeID-7cyp41vXvj62jBRh7y2j6VjLXhoJ6Hoab",
                # "minAmount": 25
            }
        else:
            raise HTTPException(status_code=400, detail=f"integration not defined for chain {chain_id} and token {token_address}")

    @staticmethod
    async def perform_staking_action(legacy: Legacy, api_action: str, action: str):
        STAKEKIT_API_KEY = os.getenv("STAKEKIT_API_KEY")
        STAKEKIT_BASE_URL = os.getenv("STAKEKIT_BASE_URL")
        try:
            investment_wallet = await InvestmentWalletService.get_investment_wallet(legacy.id)
            #wallet = WalletService.get_wallet_from_index(investment_wallet.index)
            w3 = Web3()
            operator_private_key = os.getenv("OPERATOR_PRIVATE_KEY")
            wallet = w3.eth.account.from_key(operator_private_key)
            
            async with httpx.AsyncClient(timeout=timeouts) as session:
                
                try:
                    integration = StakeKitService.get_stakekit_integration_id(legacy.chain_id, legacy.token_address)
                    integrationInfo = await StakeKitService.get_yield_info(integration["id"])
                    minAmount = integrationInfo["args"]["enter"]["args"]["amount"]["minimum"]
                    validatorAddress = integrationInfo["metadata"]["defaultValidator"]
                    decimals = integrationInfo["token"]["decimals"]
                    amount = float(legacy.amount) / (10 ** decimals)

                    if amount < minAmount:
                        raise HTTPException(status_code=400, detail=f"Legacy amount is less than the minimum amount for {action}ing")

                    response = await session.post(
                        f"{STAKEKIT_BASE_URL}/actions/{api_action}",
                        headers={"Content-Type": "application/json", "X-API-KEY": STAKEKIT_API_KEY},
                        json={
                            "integrationId": integration["id"],
                            "addresses": {"address": wallet.address},
                            "args": {"amount": str(amount), "validatorAddress": validatorAddress },
                        },
                    )
                    stake_session_response = response.json()
                    print("StakeKit Response:", stake_session_response)
                except httpx.RequestError as e:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Error connecting with {action}ing provider"
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
                            detail=f"Error getting gas for {action}ing: {str(e)}"
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
                            detail=f"Error constructing {action}ing transaction: {str(e)}"
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
                "status": f"{action}ed successfully",
                "transaction_url": status_response["url"]
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error {action}ing legacy {legacy.id}: {str(e.with_traceback())}")

    @staticmethod
    async def get_stake_balance(legacy: Legacy):
        """Obtiene el balance de staking del usuario."""
        STAKEKIT_API_KEY = os.getenv("STAKEKIT_API_KEY")
        STAKEKIT_BASE_URL = os.getenv("STAKEKIT_BASE_URL")
        try:
            # Obtener la integración de StakeKit para este token
            integration = StakeKitService.get_stakekit_integration_id(legacy.chain_id, legacy.token_address)
            integrationInfo = await StakeKitService.get_yield_info(integration["id"])
            validatorAddress = integrationInfo["metadata"]["defaultValidator"]
            # Crear la solicitud
            async with httpx.AsyncClient() as session:
                response = await session.post(
                    f"{STAKEKIT_BASE_URL}/yields/{integration['id']}/balances",
                    headers={"Content-Type": "application/json", "X-API-KEY": STAKEKIT_API_KEY},
                    json={
                        "addresses": {"address": "0xF43581DdC3ee095C1B11d0F46a7D87BEd423fcab"},
                        "args": {"validatorAddresses": [validatorAddress]}
                        }
                )

                # Verificar si la respuesta es exitosa
                if response.status_code != 201:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Error getting stake balance: {response.text}"
                    )

                balance_data = response.json()
                print(balance_data)
                return balance_data  # Devuelve toda la info del balance

        except httpx.RequestError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error connecting to StakeKit balance API: {str(e)}"
            )
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Internal service error: {str(e)}"
            )