from .constants import eth_web3, w3
from web3 import Web3


def is_address_eoa(address, l1=True):
    address = Web3.toChecksumAddress(address)
    if l1:
        is_eoa = eth_web3.eth.get_code(address).hex() == "0x"
    else:
        is_eoa = w3.eth.get_code(address).hex() == "0x"

    return is_eoa
