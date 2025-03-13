from enum import IntEnum

class Chain(IntEnum):
    EthereumMainnet = 1
    AvalancheMainnet = 43114
    
    @staticmethod
    def is_supported(chain_id: int) -> bool:
        return chain_id in [Chain.EthereumMainnet, Chain.AvalancheMainnet]
    
    @staticmethod
    def get_network_name(chain_id: int) -> str:
        if chain_id == Chain.EthereumMainnet:
            return "Ethereum Mainnet"
        elif chain_id == Chain.AvalancheMainnet:
            return "Avalanche Mainnet"
        else:
            return "Unknown Network" 