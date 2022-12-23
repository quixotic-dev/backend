from web3 import Web3
import json
from hexbytes import HexBytes

class HexJsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, HexBytes):
            return obj.hex()
        return super().default(obj)


def to_checksum_address(address):
    assert address.startswith("0x")
    if int(address, 16) == 0:
        return "0x" + "0" * 64
    else:
        return Web3.toChecksumAddress(address)


def to_checksum_address_from_bytes(address_bytes):
    address = "0x" + hex(int(address_bytes, 16))[2:].zfill(40)
    if int(address, 16) == 0:
        return address
    else:
        return Web3.toChecksumAddress(address)
