import os
from web3 import Web3
from fastapi import HTTPException
from dotenv import load_dotenv
from eth_account import Account
from app.models.investment_wallet import InvestmentWallet
from web3 import Web3

load_dotenv()

class WalletService:
    """Service for wallet operations"""
    
    @staticmethod
    def get_wallet_from_private_key(private_key: str = None):
        """Get a wallet from a private key or from environment variable"""
        try:
            w3 = Web3()
            
            # Use provided private key or get from environment
            if not private_key:
                private_key = os.getenv("OPERATOR_PRIVATE_KEY")
                
            if not private_key:
                raise ValueError("No private key provided and OPERATOR_PRIVATE_KEY not set")
                
            account = w3.eth.account.from_key(private_key)
            return account
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error creating wallet: {str(e)}"
            )
    
    @staticmethod
    def get_wallet_from_mnemonic(mnemonic: str = None):
        """Get a wallet from a mnemonic phrase or from environment variable"""
        try:
            w3 = Web3()
            
            # Use provided mnemonic or get from environment
            if not mnemonic:
                mnemonic = os.getenv("WALLET_MNEMONIC_PHRASE")
                
            if not mnemonic:
                raise ValueError("No mnemonic provided and WALLET_MNEMONIC_PHRASE not set")
                
            account = w3.eth.account.from_mnemonic(mnemonic)
            return account
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error creating wallet from mnemonic: {str(e)}"
            )
    
    @staticmethod
    def get_wallet_from_index(index: int = 0, mnemonic: str = None):
        """Get a wallet from a specific index using a mnemonic phrase"""
        try:
            w3 = Web3()
            
            # Use provided mnemonic or get from environment
            if not mnemonic:
                mnemonic = os.getenv("WALLET_MNEMONIC_PHRASE")
                
            if not mnemonic:
                raise ValueError("No mnemonic provided and WALLET_MNEMONIC_PHRASE not set")
            
            # Generate HD path for the specified index
            # m/44'/60'/0'/0/{index}
            account_path = f"m/44'/60'/0'/0/{index}"
            
            Account.enable_unaudited_hdwallet_features()
            # Derive account from mnemonic and path
            account = w3.eth.account.from_mnemonic(
                mnemonic,
                account_path=account_path
            )
            
            return account
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error creating wallet from index {index}: {str(e)}"
            )

    @staticmethod
    def get_balance(address: str, chain_id: int):
        """Get balance for a wallet address on a specific chain"""
        try:
            web3_url = os.getenv(f"WEB3_URL_{chain_id}")
            if not web3_url:
                raise ValueError(f"No web3 URL configured for chain ID {chain_id}")
                
            w3 = Web3(Web3.HTTPProvider(web3_url))
            balance_wei = w3.eth.get_balance(address)
            balance_eth = w3.from_wei(balance_wei, 'ether')
            
            return {
                "address": address,
                "chain_id": chain_id,
                "balance_wei": str(balance_wei),
                "balance_eth": str(balance_eth)
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error getting wallet balance: {str(e)}"
            )
    
    @staticmethod
    def get_token_balance(address: str, token_address: str, chain_id: int):
        """Get token balance for a wallet address on a specific chain"""
        try:
            web3_url = os.getenv(f"WEB3_URL_{chain_id}")
            if not web3_url:
                raise ValueError(f"No web3 URL configured for chain ID {chain_id}")
                
            w3 = Web3(Web3.HTTPProvider(web3_url))
            
            # ERC20 ABI - only functions we need
            abi = [
                {
                    "constant": True,
                    "inputs": [{"name": "_owner", "type": "address"}],
                    "name": "balanceOf",
                    "outputs": [{"name": "balance", "type": "uint256"}],
                    "type": "function"
                },
                {
                    "constant": True,
                    "inputs": [],
                    "name": "decimals",
                    "outputs": [{"name": "", "type": "uint8"}],
                    "type": "function"
                },
                {
                    "constant": True,
                    "inputs": [],
                    "name": "symbol",
                    "outputs": [{"name": "", "type": "string"}],
                    "type": "function"
                }
            ]
            
            # Create contract instance
            token_contract = w3.eth.contract(address=token_address, abi=abi)
            
            # Get token balance
            balance_wei = token_contract.functions.balanceOf(address).call()
            
            # Get token decimals
            try:
                decimals = token_contract.functions.decimals().call()
            except:
                decimals = 18  # Default to 18 if decimals function fails
                
            # Get token symbol
            try:
                symbol = token_contract.functions.symbol().call()
            except:
                symbol = "UNKNOWN"  # Default if symbol function fails
                
            # Calculate balance in token units
            balance_token = balance_wei / (10 ** decimals)
            
            return {
                "address": address,
                "token_address": token_address,
                "chain_id": chain_id,
                "symbol": symbol,
                "decimals": decimals,
                "balance_wei": str(balance_wei),
                "balance_token": str(balance_token)
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error getting token balance: {str(e)}"
            )
