from eth_utils import keccak
from hexbytes import HexBytes
from eth_account import _utils
from eth_keys import keys
from ..constants import EXCHANGE_CONTRACT_V6_ADDRESS, CHAIN_ID
from ..ExchangeContract import order_json_to_order_hash
from ..email_utils import send_email_about_signatures


class SignatureValidationFailed(Exception):
    pass


# Returns the domain hash for a given chain ID.
def getDomainHash(chainId):
    structured_data = {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ]
        },
        "primaryType": "EIP712Domain",
        "domain": {
            "name": "Seaport",
            "version": "1.1",
            "chainId": chainId,
            "verifyingContract": EXCHANGE_CONTRACT_V6_ADDRESS,
        },
    }

    return _utils.structured_data.hashing.hash_domain(structured_data).hex()


# Converts a 64-byte compact signature to a 65-byte "canonical" signature. Most of the time, this function will simply append
# a '00' to the compact signature. For further explanation, see in EIP-2098: https://eips.ethereum.org/EIPS/eip-2098
def to_canonical_signature(compact_signature):
    unprefixed = compact_signature[2:]

    # Splits the compact signature into two equal halves
    r_str = unprefixed[: len(unprefixed) // 2]  # First half
    yParityAndS_str = unprefixed[len(unprefixed) // 2 :]  # Second half

    # Converts hex string into its integer representation
    yParityAndS = int(yParityAndS_str, 16)

    # Performs bitwise operations to convert the compact signature into its canonical form
    s = yParityAndS & ((1 << 255) - 1)
    yParity = yParityAndS >> 255

    # Converts `s` to a hex string and removes the '0x' prefix.
    s_str_unpadded = hex(s)[2:]

    # Left-pads missing zeros
    num_zeros = 64 - len(s_str_unpadded)
    s_str = num_zeros * "0" + s_str_unpadded

    # Converts `yParity` into hex string form
    yParity_str = "0" + str(yParity)

    return "0x" + r_str + s_str + yParity_str


# Checks whether or not the offerer signed the order hash on the specified chain ID.
def is_valid_offer(offererAddress, compact_signature, orderHash, chainId=CHAIN_ID):
    domainHash = getDomainHash(chainId)
    fullOrderHash = "0x1901" + domainHash + orderHash[2:]
    digest = keccak(hexstr=fullOrderHash)

    signature = to_canonical_signature(compact_signature)
    signature_obj = keys.Signature(HexBytes(signature))
    recoveredAddress = signature_obj.recover_public_key_from_msg_hash(HexBytes(digest))

    return recoveredAddress.to_checksum_address() == offererAddress


def validate_order_signature(order_json, order_hash):
    order_dict = dict(order_json)
    signature = order_dict["signature"]
    offerer_address = order_dict["parameters"]["offerer"]
    is_valid = is_valid_offer(offerer_address, signature, order_hash)
    if not is_valid:
        # send_email_about_signatures(order_dict, order_hash)
        raise SignatureValidationFailed("Signature validation failed")
