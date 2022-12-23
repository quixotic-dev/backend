import typing

from ..abis.exchange_abi import exchangeV6_abi, rewards_wrapper_abi
from .constants import (
    BLUESWEEP_CONTRACT_ADDRESS,
    EXCHANGE_CONTRACT_V6_ADDRESS,
    REWARD_WRAPPER_ADDRESS,
    w3,
)

if typing.TYPE_CHECKING:
    from ..models import Erc721SellOrder

exchange_addresses = [
    EXCHANGE_CONTRACT_V6_ADDRESS,
    BLUESWEEP_CONTRACT_ADDRESS,
    REWARD_WRAPPER_ADDRESS,
]
exchange_contract_v6 = w3.eth.contract(
    address=EXCHANGE_CONTRACT_V6_ADDRESS, abi=exchangeV6_abi
)

rewards_wrapper_contract = w3.eth.contract(
    address=REWARD_WRAPPER_ADDRESS, abi=rewards_wrapper_abi
)


def order_is_active(order):
    if order.contract_version < 6:
        return False
    elif order.contract_version == 6:
        (
            is_validated,
            is_cancelled,
            total_filled,
            total_size,
        ) = exchange_contract_v6.functions.getOrderStatus(order.message_hash).call()
        already_filled = total_filled > 0 and (total_filled == total_size)
        return not already_filled and not is_cancelled
    return not is_cancelled


# TODO: check contract on token network
def sell_order_is_active(sell_order: "Erc721SellOrder"):
    if sell_order.contract_version == 6:
        (
            is_validated,
            is_cancelled,
            total_filled,
            total_size,
        ) = exchange_contract_v6.functions.getOrderStatus(
            sell_order.message_hash
        ).call()
        already_filled = total_filled > 0 and (total_filled == total_size)
        return not already_filled and not is_cancelled
    else:
        raise Exception("Unrecognized sell order version")


def order_json_to_order_hash(
    order_json: dict,
) -> str:  # TODO Fix this because it doesn't work
    order_params_dict = order_json["parameters"]
    order_hash = exchange_contract_v6.functions.getOrderHash(
        order_params_dict
    ).call()  # This doesn't encode the args correctly. Seems to be related to web3.py
    return order_hash
