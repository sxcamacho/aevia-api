from fastapi import APIRouter
from app.models.contract import Contract
from app.services.contract import ContractService

router = APIRouter(
    prefix="/contracts",
    tags=["contracts"]
)

@router.get("", status_code=200)
async def get_contracts():
    return await ContractService.get_contracts()

@router.get("/{name}/{chain_id}", status_code=200)
async def get_contract_by_chain_and_name(name: str, chain_id: int):
    return await ContractService.get_contract_by_chain_and_name(name, chain_id)

@router.post("", status_code=200)
async def create_contract(contract: Contract):
    return await ContractService.create_contract(contract)
