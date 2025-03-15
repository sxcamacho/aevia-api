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
from datetime import datetime, timezone
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
    async def post_action(session, wallet, legacy, api_action, action):
        try:
            integration = StakeKitService.get_stakekit_integration_id(legacy.chain_id, legacy.token_address)
            integration_info = await StakeKitService.get_yield_info(integration["id"])
            min_amount = integration_info["args"]["enter"]["args"]["amount"]["minimum"]
            validator_address = integration_info["metadata"]["defaultValidator"]
            decimals = integration_info["token"]["decimals"]
            amount = float(legacy.amount) / (10 ** decimals)

            if amount < min_amount:
                raise HTTPException(status_code=400, detail=f"Legacy amount is less than the minimum amount for {action}")

            response = await session.post(
                f"{StakeKitService.BASE_URL}/actions/{api_action}",
                headers={"Content-Type": "application/json", "X-API-KEY": StakeKitService.API_KEY},
                json={
                    "integrationId": integration["id"],
                    "addresses": {"address": wallet.address},
                    "args": {"amount": str(amount), "validatorAddress": validator_address},
                },
            )
            response_json = response.json()
            if "message" in response_json:
                error_message = response_json["message"]
                error_details = response_json.get("details", {}).get("reason", "")
                
                if error_details:
                    error_message = f"{error_message} - {error_details}"

                raise HTTPException(
                    status_code=response_json.get("code", 400),
                    detail=f"StakeKit API error: {error_message}"
                )

            return response_json
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error connecting with {action} provider: {str(e)}"
            )
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Internal service error: {str(e)}"
            )

    @staticmethod
    async def get_current_gas(session, action):
        try:
            response = await session.get(
                f"{StakeKitService.BASE_URL}/transactions/gas/ethereum",
                headers={"Accept": "application/json", "X-API-KEY": StakeKitService.API_KEY},
            )
            return response.json()
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error getting gas for {action}: {str(e)}"
            )
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Internal service error: {str(e)}"
            )

    @staticmethod
    async def construct_transaction(session, action, partial_tx, gas_args):
        try:
            response = await session.patch(
                f"{StakeKitService.BASE_URL}/transactions/{partial_tx['id']}",
                headers={"Accept": "application/json", "X-API-KEY": StakeKitService.API_KEY},
                json={"gasArgs": gas_args},
            )
            return response.json()
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error constructing {action} transaction: {str(e)}"
            )
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Internal service error: {str(e)}"
            )

    @staticmethod
    async def submit_transaction(session, action, partial_tx, signed_tx_hex):
        try:
            await session.post(
                f"{StakeKitService.BASE_URL}/transactions/{partial_tx['id']}/submit",
                headers={"Accept": "application/json", "X-API-KEY": StakeKitService.API_KEY},
                json={"signedTransaction": signed_tx_hex},
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error sending {action} transaction: {str(e)}"
            )
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Internal service error: {str(e)}"
            )

    @staticmethod
    async def get_transaction_status(session, action, partial_tx):
        try:
            response = await session.get(
                f"{StakeKitService.BASE_URL}/transactions/{partial_tx['id']}/status",
                headers={"Accept": "application/json", "X-API-KEY": StakeKitService.API_KEY},
            )
            return response.json()
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error getting {action} transaction status: {str(e)}"
            )
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Internal service error: {str(e)}"
            )

    @staticmethod
    async def execute_transaction_flow(session, wallet, action_type, transactions):
        """
        Maneja el flujo completo de transacción:
        1. Construcción de gas.
        2. Construcción de transacción.
        3. Firma y envío de la transacción.
        4. Verificación de estado.
        """
        w3 = Web3()

        for i, partial_tx in enumerate(transactions):
            if partial_tx["status"] == "SKIPPED":
                continue

            print(f"Action {i + 1} out of {len(transactions)}: {partial_tx['type']}")

            gas_response = await StakeKitService.get_current_gas(session, action_type)
            constructed_transaction_response = await StakeKitService.construct_transaction(
                session, action_type, partial_tx, gas_response["modes"]["values"][1]["gasArgs"]
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

            signed_tx_hex = "0x" + signed_tx.raw_transaction.hex()
            await StakeKitService.submit_transaction(session, action_type, partial_tx, signed_tx_hex)

            # Verificar estado de la transacción
            while True:
                status_response = await StakeKitService.get_transaction_status(session, action_type, partial_tx)
                if not status_response or "status" not in status_response:
                    raise HTTPException(
                        status_code=500,
                        detail=f"StakeKit API did not return a valid transaction status. Response: {status_response}"
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

        return {"status": f"{action_type} successfully executed"}

    @staticmethod
    async def perform_staking_action(legacy: Legacy, api_action: str):
        """Ejecuta staking o unstaking en StakeKit."""
        try:
            investment_wallet = await InvestmentWalletService.get_investment_wallet(legacy.id)
            w3 = Web3()
            operator_private_key = os.getenv("OPERATOR_PRIVATE_KEY")
            wallet = w3.eth.account.from_key(operator_private_key)
            action = "stake" if api_action == "enter" else "unstake"

            async with httpx.AsyncClient(timeout=timeouts) as session:
                stake_session_response = await StakeKitService.post_action(session, wallet, legacy, api_action, action)
                print("StakeKit Response:", stake_session_response)

                if "transactions" not in stake_session_response:
                    raise HTTPException(
                        status_code=400, detail=f"Failed to create transaction for {action}"
                    )

                return await StakeKitService.execute_transaction_flow(
                    session, wallet, action, stake_session_response["transactions"]
                )
        except HTTPException as e:
            raise e
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error executing {action}: {str(e.with_traceback())}")

    @staticmethod
    async def get_stake_balance(legacy: Legacy):
        """Obtiene el balance de staking del usuario."""
        try:
            investment_wallet = await InvestmentWalletService.get_investment_wallet(legacy.id)
            #wallet = WalletService.get_wallet_from_index(investment_wallet.index)
            w3 = Web3()
            operator_private_key = os.getenv("OPERATOR_PRIVATE_KEY")
            wallet = w3.eth.account.from_key(operator_private_key)

            # Obtener la integración de StakeKit para este token
            integration = StakeKitService.get_stakekit_integration_id(legacy.chain_id, legacy.token_address)
            integrationInfo = await StakeKitService.get_yield_info(integration["id"])
            validatorAddress = integrationInfo["metadata"]["defaultValidator"]
            # Crear la solicitud
            async with httpx.AsyncClient() as session:
                response = await session.post(
                    f"{StakeKitService.BASE_URL}/yields/{integration['id']}/balances",
                    headers={"Content-Type": "application/json", "X-API-KEY": StakeKitService.API_KEY},
                    json={
                        "addresses": {"address": wallet.address},
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

    @staticmethod
    def format_balance_data(balance_data):
        formatted_data = []
        for item in balance_data:
            formatted_data.append({
                "id": item["groupId"],
                "type": item["type"],
                "amount": item["amount"],
                "date": item.get("date"),
                "network": item["token"]["network"],
                "token_symbol": item["token"]["symbol"],
                "pendingActions": item["pendingActions"],
            })
        return formatted_data

    @staticmethod
    async def post_pending_action(session, integration_id: str, entry, action_type: str):
        """Ejecuta la acción CLAIM_UNSTAKED o CLAIM_REWARDS en StakeKit."""
        try:
            # Buscar la acción pendiente que coincida con action_type
            matching_action = next(
                (pa for pa in entry.get("pendingActions", []) if pa.get("type") == action_type), 
                None
            )
            if not matching_action:
                raise HTTPException(
                    status_code=400, 
                    detail=f"No pending action of type '{action_type}' found."
                )

            passthrough = matching_action.get("passthrough")
            amount = entry.get("amount")
            validator_address = entry.get("validatorAddress")

            response = await session.post(
                f"{StakeKitService.BASE_URL}/actions/pending",
                headers={"Content-Type": "application/json", "X-API-KEY": StakeKitService.API_KEY},
                json={
                    "type": action_type,
                    "integrationId": integration_id,
                    "passthrough": passthrough,
                    "args": {"amount": amount, "validatorAddress": validator_address},
                },
            )
            print("Raw Response:", response.text)
            return response.json()
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"Error connecting to StakeKit: {str(e)}")
   
    @staticmethod
    async def perform_pending_action(legacy: Legacy, action_type: str):
        """Ejecuta una acción pendiente como CLAIM_UNSTAKED, CLAIM_REWARDS o WITHDRAW_ALL."""
        try:
            investment_wallet = await InvestmentWalletService.get_investment_wallet(legacy.id)
            w3 = Web3()
            operator_private_key = os.getenv("OPERATOR_PRIVATE_KEY")
            wallet = w3.eth.account.from_key(operator_private_key)

            async with httpx.AsyncClient(timeout=timeouts) as session:
                integration = StakeKitService.get_stakekit_integration_id(legacy.chain_id, legacy.token_address)
                stake_balance = await StakeKitService.get_stake_balance(legacy)

                # Filtrar las acciones pendientes según el tipo de acción
                if action_type == "CLAIM_REWARDS":
                    claimable_entries = [
                     entry for entry in stake_balance 
                        if entry["type"] == "rewards"
                    ]
                elif action_type == "WITHDRAW":
                    claimable_entries = [
                        entry for entry in stake_balance 
                        if entry["type"] == "unstaked"
                    ]
                else:
                    raise HTTPException(status_code=400, detail=f"Invalid action type: {action_type}")

                if not claimable_entries:
                    return False

                for entry in claimable_entries:
                    # Para WITHDRAW, verificar la fecha antes de reclamar
                    if action_type == "WITHDRAW" and "date" in entry:
                        unstake_date = datetime.fromisoformat(entry["date"])
                        if unstake_date > datetime.now(timezone.utc):
                            continue  # Aún no está listo para reclamar

                    # Ejecutar la acción pendiente
                    pending_response = await StakeKitService.post_pending_action(
                        session, integration["id"], entry, action_type
                    )
                    print(f"Pending Action Response ({action_type}):", pending_response)

                    if "transactions" not in pending_response:
                        raise HTTPException(
                            status_code=400, detail=f"Failed to create transaction for {action_type}"
                        )

                    await StakeKitService.execute_transaction_flow(
                        session, wallet, action_type, pending_response["transactions"]
                    )
                    return True
        except HTTPException as e:
            raise e
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error executing {action_type}: {str(e.with_traceback())}")


    @staticmethod
    async def claim(legacy: Legacy):
        """Ejecuta el proceso de claiming en StakeKit."""
       
        # Ejecuta las acciones de claim (rewards)
        are_rewards = await StakeKitService.perform_pending_action(legacy, "CLAIM_REWARDS")
        if not are_rewards:
            return {"status": "Nothing to claim"}
        return {"status": "Claim process completed"}

    
    @staticmethod
    async def withdraw(legacy: Legacy):
        """Ejecuta el proceso de retiro de todos los fondos disponibles en StakeKit."""

        are_withdrawn = await StakeKitService.perform_pending_action(legacy, "WITHDRAW")
        if not are_withdrawn:
            return {"status": "Nothing to withdraw"}
        return {"status": "Withdraw process completed"}