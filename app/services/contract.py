from fastapi import HTTPException
from app.config.database import supabase
from app.models.contract import Contract

class ContractService:
    @staticmethod
    async def get_contracts():
        try:
            response = supabase.table('contracts').select('*').execute()
            return response.data
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error retrieving contracts information: {str(e)}"
            )

    @staticmethod
    async def get_contract_by_chain_and_name(contract_name: str, chain_id: int):
        try:
            response = supabase.table('contracts').select('*').eq('chain_id', chain_id).eq('name', contract_name).execute()
            
            if not response.data:
                raise HTTPException(
                    status_code=404,
                    detail=f"Contract {contract_name} not found for chain ID {chain_id}"
                )
                
            return Contract(**response.data[0])
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error retrieving contract information: {str(e)}"
            )

    @staticmethod
    async def create_contract(contract: Contract):
        try:
            result = supabase.table("contracts").insert({
                "chain_id": contract.chainId,
                "address": contract.address,
                "name": contract.name,
                "abi": contract.abi
            }).execute()

            return result.data[0]
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error creacting contract: {str(e)}"
            )
