import os
import httpx
from fastapi import HTTPException
from dotenv import load_dotenv
from app.enums.chain import Chain
from app.enums.token import Token

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
    def get_stakekit_integration_info(chain_id: int, token_address: str):
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
