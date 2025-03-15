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
    async def post_action(session, wallet, legacy, api_action, log_action):
        try:
            integration = StakeKitService.get_stakekit_integration_id(legacy.chain_id, legacy.token_address)
            integration_info = await StakeKitService.get_yield_info(integration["id"])
            min_amount = integration_info["args"]["enter"]["args"]["amount"]["minimum"]
            validator_address = integration_info["metadata"]["defaultValidator"]
            decimals = integration_info["token"]["decimals"]
            amount = float(legacy.amount) / (10 ** decimals)

            if amount < min_amount:
                raise HTTPException(status_code=400, detail=f"Legacy amount is less than the minimum amount for {log_action}")

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
                detail=f"Error connecting with {log_action} provider: {str(e)}"
            )
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Internal service error: {str(e)}"
            )

    @staticmethod
    async def get_current_gas(session, log_action):
        try:
            response = await session.get(
                f"{StakeKitService.BASE_URL}/transactions/gas/ethereum",
                headers={"Accept": "application/json", "X-API-KEY": StakeKitService.API_KEY},
            )
            return response.json()
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error getting gas for {log_action}: {str(e)}"
            )
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Internal service error: {str(e)}"
            )

    @staticmethod
    async def construct_transaction(session, log_action, partial_tx, gas_args):
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
                detail=f"Error constructing {log_action} transaction: {str(e)}"
            )
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Internal service error: {str(e)}"
            )

    @staticmethod
    async def submit_transaction(session, log_action, partial_tx, signed_tx_hex):
        try:
            await session.post(
                f"{StakeKitService.BASE_URL}/transactions/{partial_tx['id']}/submit",
                headers={"Accept": "application/json", "X-API-KEY": StakeKitService.API_KEY},
                json={"signedTransaction": signed_tx_hex},
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error sending {log_action} transaction: {str(e)}"
            )
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Internal service error: {str(e)}"
            )

    @staticmethod
    async def get_transaction_status(session, log_action, partial_tx):
        try:
            response = await session.get(
                f"{StakeKitService.BASE_URL}/transactions/{partial_tx['id']}/status",
                headers={"Accept": "application/json", "X-API-KEY": StakeKitService.API_KEY},
            )
            return response.json()
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error getting {log_action} transaction status: {str(e)}"
            )
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Internal service error: {str(e)}"
            )

    @staticmethod
    async def execute_transaction_flow(session, wallet, log_action, transactions):
        """ Handles the complete transaction flow:
        1. Gas estimation.
        2. Transaction construction.
        3. Signing and submitting the transaction.
        4. Status verification.
        """
        w3 = Web3()

        for i, partial_tx in enumerate(transactions):
            if partial_tx["status"] == "SKIPPED":
                continue

            print(f"Action {i + 1} out of {len(transactions)}: {partial_tx['type']}")

            gas_response = await StakeKitService.get_current_gas(session, log_action)
            constructed_transaction_response = await StakeKitService.construct_transaction(
                session, log_action, partial_tx, gas_response["modes"]["values"][1]["gasArgs"]
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
            await StakeKitService.submit_transaction(session, log_action, partial_tx, signed_tx_hex)

            # Verify transaction status
            while True:
                status_response = await StakeKitService.get_transaction_status(session, log_action, partial_tx)
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

        return {"status": f"{log_action} successfully executed"}

    @staticmethod
    async def perform_staking_action(legacy: Legacy, api_action: str):
        """Executes staking or unstaking in StakeKit."""
        try:
            investment_wallet = await InvestmentWalletService.get_investment_wallet(legacy.id)
            wallet = WalletService.get_wallet_from_index(investment_wallet.index)
            log_action = "stake" if api_action == "enter" else "unstake"

            async with httpx.AsyncClient(timeout=timeouts) as session:
                stake_session_response = await StakeKitService.post_action(session, wallet, legacy, api_action, log_action)
                print("StakeKit Response:", stake_session_response)

                if "transactions" not in stake_session_response:
                    raise HTTPException(
                        status_code=400, detail=f"Failed to create transaction for {log_action}"
                    )

                return await StakeKitService.execute_transaction_flow(
                    session, wallet, log_action, stake_session_response["transactions"]
                )
        except HTTPException as e:
            raise e
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error executing {log_action}: {str(e.with_traceback())}")

    @staticmethod
    async def get_stake_balance(legacy: Legacy):
        """Retrieves the user's staking balance."""
        try:
            investment_wallet = await InvestmentWalletService.get_investment_wallet(legacy.id)
            wallet = WalletService.get_wallet_from_index(investment_wallet.index)

            # Get the StakeKit integration for this token
            integration = StakeKitService.get_stakekit_integration_id(legacy.chain_id, legacy.token_address)
            integrationInfo = await StakeKitService.get_yield_info(integration["id"])
            validatorAddress = integrationInfo["metadata"]["defaultValidator"]
            # Create the request
            async with httpx.AsyncClient() as session:
                response = await session.post(
                    f"{StakeKitService.BASE_URL}/yields/{integration['id']}/balances",
                    headers={"Content-Type": "application/json", "X-API-KEY": StakeKitService.API_KEY},
                    json={
                        "addresses": {"address": wallet.address},
                        "args": {"validatorAddresses": [validatorAddress]}
                        }
                )

                # Verify if the response is successful
                if response.status_code != 201:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Error getting stake balance: {response.text}"
                    )

                balance_data = response.json()
                print(balance_data)
                return balance_data  # Returns all balance information

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
    async def post_pending_action(session, integration_id: str, entry, action):
        """Executes a pending action in StakeKit."""
        try:
            amount = entry.get("amount")
            validator_address = entry.get("validatorAddress")
            action_type = action.get("type")
            passthrough = action.get("passthrough")

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
    async def perform_pending_actions(legacy: Legacy):
        """Executes all pending actions in StakeKit."""
        try:
            investment_wallet = await InvestmentWalletService.get_investment_wallet(legacy.id)
            wallet = WalletService.get_wallet_from_index(investment_wallet.index)

            async with httpx.AsyncClient(timeout=timeouts) as session:
                results = []
                integration = StakeKitService.get_stakekit_integration_id(legacy.chain_id, legacy.token_address)
                stake_balance = await StakeKitService.get_stake_balance(legacy)

                executable_entries = [
                    entry for entry in stake_balance
                    if "pendingActions" in entry and entry["pendingActions"]  # Checks if there are pending actions
                ]
                for entry in executable_entries:
                    groupId = entry.get("groupId")
                    pending_actions = entry.get("pendingActions", [])
                    for action in pending_actions:
                        action_type = action.get("type")
                        # Execute the pending action
                        pending_response = await StakeKitService.post_pending_action(
                            session, integration["id"], entry, action
                        )
                        print(f"Pending Action Response ({groupId}):", pending_response)

                        if "transactions" not in pending_response:
                            raise HTTPException(
                                status_code=400, detail=f"Failed to create transaction for {action_type}"
                            )

                        response = await StakeKitService.execute_transaction_flow(
                            session, wallet, action_type, pending_response["transactions"]
                        )
                        results.append({groupId: response})
                return results
        except HTTPException as e:
            raise e
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error executing pending actions: {str(e)}")
    
    @staticmethod
    async def withdraw(legacy: Legacy):
        """Executes the process of withdrawing all available funds in StakeKit."""

        results = await StakeKitService.perform_pending_actions(legacy)
        if not results:
            return {"status": "Nothing to withdraw"}
        return results