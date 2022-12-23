import jsonschema
from .json_schemas import sell_order_schema, buy_order_schema
from ...models import Contract, Erc721Collection
from ..constants import MARKETPLACE_FEE, MARKETPLACE_PAYOUT_ADDRESS
from .validate_order import validate_order_signature


def is_close(num1, num2):
    num1 = int(num1)
    num2 = int(num2)
    return abs(num1 - num2) / min(num1, num2) < 0.001


def validate_sell_order_fees(sell_order_json):
    consideration = sell_order_json["parameters"]["consideration"]
    offer = sell_order_json["parameters"]["offer"]

    assert all(
        item["startAmount"] == item["endAmount"] for item in consideration
    ), "Start amount and end amount must be the same"

    assert all(
        int(item["startAmount"]) > 0 for item in consideration
    ), "All consideration amounts must be creator than 0."

    assert all(
        item["startAmount"] == item["endAmount"] for item in offer
    ), "Start amount and end amount must be the same"

    assert all(
        int(item["startAmount"]) > 0 for item in offer
    ), "All offer amounts must be creator than 0."

    assert (
        len(
            set(
                item["token"] for item in sell_order_json["parameters"]["consideration"]
            )
        )
        == 1
    ), "A sell order must contain only one kind of token"

    marketplace_fee_item, proceeds_item, royalty_fee_item = None, None, None
    if len(consideration) == 2:
        marketplace_fee_item, proceeds_item = consideration
    elif len(consideration) == 3:
        marketplace_fee_item, proceeds_item, royalty_fee_item = consideration
    else:
        raise Exception(f"Consideration is of unknown length: {consideration}")

    final_sale_price = sum(int(item["startAmount"]) for item in consideration)

    # Check marketplace fee
    expected_marketplace_fee_amount = round(final_sale_price * MARKETPLACE_FEE)
    assert is_close(
        marketplace_fee_item["startAmount"], expected_marketplace_fee_amount
    ), f"Marketplace fee is not valid: '{marketplace_fee_item['startAmount']}' is not '{expected_marketplace_fee_amount}'"

    assert (
        marketplace_fee_item["recipient"] == MARKETPLACE_PAYOUT_ADDRESS
    ), f"Payout address is not valid: {marketplace_fee_item}"

    # Check royalty
    collection_address = sell_order_json["parameters"]["offer"][0]["token"]
    smart_contract = Contract.objects.get(address=collection_address)
    royalty_per_mille = smart_contract.collection.royalty_per_mille

    if royalty_per_mille:
        royalty_payout_address = smart_contract.collection.payout_address
        expected_royalty_fee = round(final_sale_price * (royalty_per_mille / 1000))
        assert is_close(
            royalty_fee_item["startAmount"], expected_royalty_fee
        ), f"Royalty fee is not valid: '{royalty_fee_item['startAmount']}' is not '{expected_royalty_fee}'"

        assert (
            royalty_fee_item["recipient"] == royalty_payout_address
        ), f"Payout address is not valid: {royalty_fee_item}"
    else:
        expected_royalty_fee = 0

    # Check proceeds
    expected_proceeds = final_sale_price - (
        expected_marketplace_fee_amount + expected_royalty_fee
    )
    offerer_address = sell_order_json["parameters"]["offerer"]
    assert is_close(
        proceeds_item["startAmount"], expected_proceeds
    ), f"Proceeds amount is not valid: '{proceeds_item['startAmount']}' is not '{expected_proceeds}'"

    assert (
        proceeds_item["recipient"] == offerer_address
    ), f"Proceeds address is not valid: {offerer_address}"


def validate_buy_order_fees(buy_order_json):
    consideration = buy_order_json["parameters"]["consideration"]
    offer = buy_order_json["parameters"]["offer"]

    offer_token = buy_order_json["parameters"]["offer"][0]["token"]
    assert all(
        item["startAmount"] == item["endAmount"] for item in consideration
    ), "Start amount and end amount must be the same"

    assert all(
        int(item["startAmount"]) > 0 for item in consideration
    ), "All consideration amounts must be creator than 0."

    assert all(
        item["startAmount"] == item["endAmount"] for item in offer
    ), "Start amount and end amount must be the same"

    assert all(
        int(item["startAmount"]) > 0 for item in offer
    ), "All offer amounts must be creator than 0."

    nft_item, marketplace_fee_item, royalty_fee_item = None, None, None
    if len(consideration) == 2:
        nft_item, marketplace_fee_item = consideration
    elif len(consideration) == 3:
        nft_item, marketplace_fee_item, royalty_fee_item = consideration
    else:
        raise Exception(f"Consideration is of unknown length: {consideration}")

    final_sale_price = int(buy_order_json["parameters"]["offer"][0]["startAmount"])

    # Check marketplace fee
    expected_marketplace_fee_amount = round(final_sale_price * MARKETPLACE_FEE)
    assert is_close(
        marketplace_fee_item["startAmount"], expected_marketplace_fee_amount
    ), f"Marketplace fee is not valid: '{marketplace_fee_item['startAmount']}' is not '{expected_marketplace_fee_amount}'"

    assert (
        marketplace_fee_item["recipient"] == MARKETPLACE_PAYOUT_ADDRESS
    ), f"Payout address is not valid: {marketplace_fee_item}"

    assert (
        marketplace_fee_item["token"] == offer_token
    ), f"Marketplace fee token is not correct: {marketplace_fee_item['token']}"

    # Check royalty
    collection_address = nft_item["token"]
    smart_contract = Contract.objects.get(address=collection_address)
    royalty_per_mille = smart_contract.collection.royalty_per_mille

    if royalty_per_mille:
        royalty_payout_address = smart_contract.collection.payout_address
        expected_royalty_fee = round(final_sale_price * (royalty_per_mille / 1000))
        assert is_close(
            royalty_fee_item["startAmount"], expected_royalty_fee
        ), f"Royalty fee is not valid: '{royalty_fee_item['startAmount']}' is not '{expected_royalty_fee}'"

        assert (
            royalty_fee_item["recipient"] == royalty_payout_address
        ), f"Payout address is not valid: {royalty_fee_item}"

        assert (
            royalty_fee_item["token"] == offer_token
        ), f"Royalty fee token is not correct: {royalty_fee_item['token']}"

    else:
        expected_royalty_fee = 0

    # Check proceeds
    offerer_address = buy_order_json["parameters"]["offerer"]
    assert (
        nft_item["recipient"] == offerer_address
    ), f"Proceeds address is not valid: {offerer_address}"


def validate_seaport_sell_order(sell_order_json, order_hash):
    jsonschema.validate(sell_order_json, sell_order_schema)
    validate_sell_order_fees(sell_order_json)
    validate_order_signature(sell_order_json, order_hash)


def validate_seaport_buy_order(buy_order_json, order_hash):
    jsonschema.validate(buy_order_json, buy_order_schema)
    validate_buy_order_fees(buy_order_json)
    validate_order_signature(buy_order_json, order_hash)
