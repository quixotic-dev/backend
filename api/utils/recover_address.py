from .constants import w3
from eth_account.messages import encode_defunct


def recover_address(message, signature):
    if not signature.startswith("0x"):
        raise Exception("Signature must start with 0x")
    if len(signature) < 3:
        raise Exception("Incomplete signature")
    encoded_message = encode_defunct(text=message)
    address = w3.eth.account.recover_message(encoded_message, signature=signature[2:])
    return address
