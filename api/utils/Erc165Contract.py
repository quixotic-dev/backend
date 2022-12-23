from web3 import Web3

from ..abis.erc165_abi import erc165_abi
from .constants import ALCHEMY_API_KEY, NETWORK, w3

ERC721InterfaceId = "0x80ac58cd"
ERC1155InterfaceId = "0xd9b67a26"


class Erc165Contract:
    def __init__(self, contract_address, network_id: str = None):
        if network_id and network_id != NETWORK:
            self.w3 = Web3(
                Web3.HTTPProvider(
                    f"https://{network_id}.g.alchemy.com/v2/{ALCHEMY_API_KEY}"
                )
            )
        else:
            self.w3 = w3

        self.contract = self.w3.eth.contract(address=contract_address, abi=erc165_abi)

    def supports_721_interface(self):
        try:
            return self.contract.functions.supportsInterface(ERC721InterfaceId).call()
        except Exception as e:
            return False

    def supports_1155_interface(self):
        try:
            return self.contract.functions.supportsInterface(ERC1155InterfaceId).call()
        except Exception as e:
            return False
