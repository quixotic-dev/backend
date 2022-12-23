from web3 import Web3

from ..abis.erc20_abi import erc20_abi
from .constants import w3


class Erc20Contract:
    def __init__(self, contract_address):
        contract_address = Web3.toChecksumAddress(contract_address)
        self.contract = w3.eth.contract(address=contract_address, abi=erc20_abi)

    def balance_of(self, address):
        address = Web3.toChecksumAddress(address)
        return self.contract.functions.balanceOf(address).call()

    def allowance(self, wallet_address, contract_address):
        wallet_address = Web3.toChecksumAddress(wallet_address)
        contract_address = Web3.toChecksumAddress(contract_address)
        return self.contract.functions.allowance(
            wallet_address, contract_address
        ).call()
