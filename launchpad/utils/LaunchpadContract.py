from api.utils.constants import w3
from .launchpad_abi import launchpad_abi


class LaunchpadContract:
    def __init__(self, contract_address):
        self.contract = w3.eth.contract(address=contract_address, abi=launchpad_abi)

    def premint_state(self):
        return self.contract.functions.greenListSaleIsActive().call()

    def mint_state(self):
        return self.contract.functions.saleIsActive().call()

    def token_by_index(self, i):
        i = int(i)
        return self.contract.functions.tokenByIndex(i).call()