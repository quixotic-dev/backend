from api.models import PaymentToken
from .constants import w3, eth_web3
from .Erc20Contract import Erc20Contract
from web3 import Web3


def get_balances(address):
    assert Web3.isChecksumAddress(address), f"{address} must be checksum address"

    try:
        data = {
            "ETH": w3.fromWei(w3.eth.get_balance(address), 'ether'),
            "L1_ETH": w3.fromWei(eth_web3.eth.get_balance(address), 'ether')
        }

        for token in PaymentToken.objects.exclude(symbol="ETH"):
            contract = Erc20Contract(token.address)
            data[token.symbol] = w3.fromWei(contract.balance_of(address), 'ether')
        return data
    except Exception as e:
        print(e)
        return {}
