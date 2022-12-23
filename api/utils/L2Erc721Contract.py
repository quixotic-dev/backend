from .constants import w3, eth_web3
from ..abis.L2_standard_token_abi import L2_standard_token_abi


class L2Erc721Contract:
    def __init__(
        self,
        contract_address,
    ):
        self.contract = w3.eth.contract(
            address=contract_address, abi=L2_standard_token_abi
        )

    def remote_token(self):
        return self.contract.functions.remoteToken().call()
