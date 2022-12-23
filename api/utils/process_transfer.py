import os
from datetime import datetime, timezone

from django.db import transaction
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Asm, From, GroupId, GroupsToDisplay, Mail, To
from web3 import Web3

from .. import models
from .constants import (
    ALCHEMY_API_KEY,
    BLUESWEEP_CONTRACT_ADDRESS,
    EXCHANGE_CONTRACT_V6_ADDRESS,
    NETWORK,
    REWARD_WRAPPER_ADDRESS,
    WEBSITE_URL,
)
from .constants import w3 as primary_w3
from .ExchangeContract import (
    exchange_addresses,
    exchange_contract_v6,
    rewards_wrapper_contract,
)
from .hex_utils import to_checksum_address_from_bytes

ERC_721_SAFE_TRANSFER_TOPIC = (
    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
)
OP_TOKEN_ADDRESS = "0x4200000000000000000000000000000000000042"


def process_fulfilled_order(trade_txn, onchain_activity, timestamp, w3):
    trade_txn_id = trade_txn["hash"].hex()
    assert (
        trade_txn["to"] in exchange_addresses
    ), f"Txn '{trade_txn_id}' is not to an exchange address"

    if (
        trade_txn["to"] == EXCHANGE_CONTRACT_V6_ADDRESS
        or trade_txn["to"] == REWARD_WRAPPER_ADDRESS
    ):
        if trade_txn["to"] == REWARD_WRAPPER_ADDRESS:
            func, inputs = rewards_wrapper_contract.decode_function_input(
                trade_txn.input
            )
            if "_order" in inputs:  # Remove this after contract variable name changes
                inputs["order"] = inputs["_order"]
            if "orders" in inputs:
                inputs["advancedOrders"] = [
                    (None, None, None, o[1]) for o in inputs["orders"]
                ]
        else:
            func, inputs = exchange_contract_v6.decode_function_input(trade_txn.input)
        try:
            if "order" in inputs:
                signature = "0x" + inputs["order"][1].hex()
                sell_order = models.Erc721SellOrder.objects.get(signature=signature)
            else:
                for order in inputs["advancedOrders"]:
                    signature = "0x" + order[3].hex()
                    sell_order = models.Erc721SellOrder.objects.get(signature=signature)
                    if sell_order.token == onchain_activity.token:
                        break
            buyer_address = trade_txn["from"]
            buyer_profile, _created = models.Profile.objects.get_or_create(
                address=buyer_address
            )

            with transaction.atomic():
                order = models.Erc721SellOrder.objects.select_for_update().get(
                    id=sell_order.id
                )
                order.fulfilled = True
                order.txn_id = trade_txn_id
                order.time_sold = timestamp
                order.buyer = buyer_profile
                order.save()

                onchain_activity.sell_order = order
        except Exception as e:
            print(e)
            try:
                signature = "0x" + inputs["parameters"][-1].hex()
                buy_order = models.Erc721BuyOrder.objects.get(signature=signature)
                seller_address = trade_txn["from"]
                seller_profile, _created = models.Profile.objects.get_or_create(
                    address=seller_address
                )

                with transaction.atomic():
                    order = models.Erc721BuyOrder.objects.select_for_update().get(
                        id=buy_order.id
                    )
                    order.fulfilled = True
                    order.txn_id = trade_txn_id
                    order.time_sold = timestamp
                    order.seller = seller_profile
                    order.save()

                    onchain_activity.buy_order = order
            except Exception as e:
                print(e)
                try:
                    if "order" in inputs:
                        signature = "0x" + inputs["order"][1].hex()
                        dutch_auction = models.Erc721DutchAuction.objects.get(
                            signature=signature
                        )
                    else:
                        for order in inputs["advancedOrders"]:
                            signature = "0x" + order[3].hex()
                            dutch_auction = models.Erc721DutchAuction.objects.get(
                                signature=signature
                            )
                            if sell_order.token == onchain_activity.token:
                                break
                    buyer_address = trade_txn["from"]
                    buyer_profile, _created = models.Profile.objects.get_or_create(
                        address=buyer_address
                    )

                    priceDiff = dutch_auction.start_price - dutch_auction.end_price
                    timeDiff = (
                        dutch_auction.end_time.timestamp()
                        - dutch_auction.start_time.timestamp()
                    )
                    timePassed = (
                        timestamp.timestamp() - dutch_auction.start_time.timestamp()
                    )
                    discount = (priceDiff / timeDiff) * timePassed
                    current_price = dutch_auction.start_price - discount

                    with transaction.atomic():
                        order = (
                            models.Erc721DutchAuction.objects.select_for_update().get(
                                id=dutch_auction.id
                            )
                        )
                        order.price = round(current_price, 5)
                        order.fulfilled = True
                        order.txn_id = trade_txn_id
                        order.time_sold = timestamp
                        order.buyer = buyer_profile
                        order.save()

                        onchain_activity.dutch_auction = order
                except Exception as e:
                    print(e)
                    pass

        onchain_activity.save()
        return onchain_activity

    if trade_txn["to"] == BLUESWEEP_CONTRACT_ADDRESS:
        buyer_address = trade_txn["from"]
        buyer_profile, _created = models.Profile.objects.get_or_create(
            address=buyer_address
        )

        if onchain_activity.to_profile == buyer_profile:
            return onchain_activity

        txn_receipt = w3.eth.get_transaction_receipt(trade_txn_id)
        for log in txn_receipt["logs"]:
            if (
                log["topics"][0].hex()
                == "0x9d9af8e38d66c62e2c12f0225249fd9d721c54b83f48d9352c97c6cacdcb6f31"
            ):
                message_hash = log["data"][0:66]
                try:
                    sell_order = models.Erc721SellOrder.objects.get(
                        message_hash=message_hash
                    )
                    if sell_order.token == onchain_activity.token:
                        sell_order.fulfilled = True
                        sell_order.txn_id = trade_txn_id
                        sell_order.time_sold = timestamp
                        sell_order.buyer = buyer_profile
                        sell_order.save()
                        onchain_activity.sell_order = sell_order
                        onchain_activity.save()
                except models.Erc721SellOrder.DoesNotExist:
                    pass

        return onchain_activity


def handle_transfer_event(transfer_event, network=NETWORK):
    transfer_txn_id = transfer_event["transactionHash"].hex()
    print(f"Processing transfer txn {transfer_txn_id}")

    contract_address = Web3.toChecksumAddress(transfer_event["address"])
    smart_contract = models.Contract.objects.get(
        address=contract_address, network__network_id=network
    )

    if smart_contract.network.network_id != NETWORK:
        w3 = Web3(
            Web3.HTTPProvider(
                f"https://{smart_contract.network.network_id}.g.alchemy.com/v2/{ALCHEMY_API_KEY}"
            )
        )
    else:
        w3 = primary_w3

    from_address = Web3.toChecksumAddress(transfer_event["args"]["from"])
    to_address = Web3.toChecksumAddress(transfer_event["args"]["to"])

    token_id = (
        transfer_event["args"]["tokenId"]
        if "tokenId" in transfer_event["args"]
        else transfer_event["args"]["id"]
    )
    quantity = (
        transfer_event["args"]["value"] if "value" in transfer_event["args"] else 1
    )

    if from_address == REWARD_WRAPPER_ADDRESS:
        txn_receipt = w3.eth.get_transaction_receipt(transfer_txn_id)
        for log in txn_receipt["logs"]:
            if (
                log["topics"][0].hex() == ERC_721_SAFE_TRANSFER_TOPIC
                and log["address"] != OP_TOKEN_ADDRESS
            ):
                __topic, __from_addr, __to_addr, __token_id = log["topics"]
                if (
                    to_checksum_address_from_bytes(__to_addr.hex())
                    == REWARD_WRAPPER_ADDRESS
                    and int(__token_id.hex(), 16) == token_id
                ):
                    from_address = to_checksum_address_from_bytes(__from_addr.hex())
                    break

    elif to_address == REWARD_WRAPPER_ADDRESS:
        print("Skipping because this is to the reward contract")
        return

    from_profile, _created = models.Profile.objects.get_or_create(address=from_address)
    to_profile, _created = models.Profile.objects.get_or_create(address=to_address)

    try:
        token = models.Erc721Token.objects.get(
            smart_contract=smart_contract, token_id=token_id
        )
    except models.Erc721Token.DoesNotExist:
        if smart_contract.type == models.CollectionType.ERC721:
            token = smart_contract.pull_erc721_token(token_id, queue=False)
        elif smart_contract.type == models.CollectionType.ERC1155:
            token = smart_contract.pull_erc1155_token(token_id, queue=False)

    # If bridged token is minted or burnt, update L1 token pending owner
    if smart_contract.is_bridged and (
        to_profile.address == "0x0000000000000000000000000000000000000000"
        or from_profile.address == "0x0000000000000000000000000000000000000000"
    ):
        try:
            bridge_relationship = models.BridgedContract.objects.get(
                to_contract=smart_contract
            )
            l1_contract = bridge_relationship.from_contract
            with transaction.atomic():
                l1_token = models.Erc721Token.objects.select_for_update().get(
                    smart_contract=l1_contract, token_id=token_id
                )
                if to_profile.address == "0x0000000000000000000000000000000000000000":
                    l1_token.pending_owner = from_profile
                    l1_token.pending_deposit = False
                else:
                    l1_token.pending_owner = None
                l1_token.save()
        except Exception as e:
            print(e)
            pass

    # If L1 token is bridged or transferred, update pending owner
    if (
        smart_contract.network.network_id == "eth-mainnet"
        or smart_contract.network.network_id == "eth-goerli"
    ):
        if (
            smart_contract.network.network_id == "eth-mainnet"
            and to_profile.address == "0x5a7749f83b81B301cAb5f48EB8516B986DAef23D"
        ) or (
            smart_contract.network.network_id == "eth-goerli"
            and to_profile.address == "0x8DD330DdE8D9898d43b4dc840Da27A07dF91b3c9"
        ):
            with transaction.atomic():
                tok = models.Erc721Token.objects.select_for_update().get(
                    smart_contract=smart_contract, token_id=token_id
                )
                tok.pending_owner = from_profile
                tok.pending_deposit = True
                tok.save()
        else:
            with transaction.atomic():
                tok = models.Erc721Token.objects.select_for_update().get(
                    smart_contract=smart_contract, token_id=token_id
                )
                tok.pending_owner = None
                tok.save()

    full_txn = w3.eth.get_transaction(transfer_txn_id)

    try:
        timestamp = datetime.fromtimestamp(
            int(full_txn["l1Timestamp"], 16), timezone.utc
        )
    except Exception:
        timestamp = datetime.fromtimestamp(
            w3.eth.getBlock(full_txn["blockNumber"]).timestamp, timezone.utc
        )

    if token.smart_contract.type == models.CollectionType.ERC1155:
        token.refresh_owner(from_profile=from_profile, to_profile=to_profile)
        token.soft_refresh_orders(from_profile=from_profile, to_profile=to_profile)
    else:
        with transaction.atomic():
            tok = models.Erc721Token.objects.select_for_update().get(
                smart_contract=smart_contract, token_id=token_id
            )
            tok.refresh_owner(from_profile=from_profile, to_profile=to_profile)

        with transaction.atomic():
            tok = models.Erc721Token.objects.select_for_update().get(
                smart_contract=smart_contract, token_id=token_id
            )

            # Mark token as airdrop if to_address is different from the address initiating the transaction
            if full_txn["from"] and full_txn["from"] != to_address:
                is_airdrop = True
            else:
                is_airdrop = False

            tok.is_airdrop = is_airdrop
            tok.save()
            tok.soft_refresh_orders()

    try:
        activity, _activity_created = models.Erc721Activity.objects.get_or_create(
            txn_id=transfer_txn_id,
            token=token,
            quantity=quantity,
            from_profile=from_profile,
            to_profile=to_profile,
            timestamp=timestamp,
        )
    except Exception as e:
        print(e)
        return

    if (
        network == NETWORK
        and full_txn["to"]
        and Web3.toChecksumAddress(full_txn["to"]) in exchange_addresses
    ):
        activity = process_fulfilled_order(full_txn, activity, timestamp, w3=w3)

    if _activity_created:
        print(f"Newly created activity: {transfer_txn_id}")

        # Send sale /purchase notification email via SendGrid
        if activity.sell_order or activity.dutch_auction or activity.buy_order:
            if activity.sell_order:
                order = activity.sell_order
                currency = activity.sell_order.payment_token.symbol
            elif activity.dutch_auction:
                order = activity.dutch_auction
                currency = activity.dutch_auction.payment_token.symbol
            else:
                order = activity.buy_order
                currency = activity.buy_order.payment_token.symbol

            if from_profile.email:
                message = Mail(
                    from_email=From("no-reply@quixotic.io", "Quix"),
                    to_emails=To(from_profile.email),
                )
                message.dynamic_template_data = {
                    "item_name": token.name,
                    "price": str(
                        Web3.fromWei(Web3.toWei(int(order.price), "gwei"), "ether")
                    ),
                    "currency": currency,
                    "item_link": WEBSITE_URL
                    + "/asset/"
                    + token.smart_contract.address
                    + "/"
                    + str(token.token_id),
                    "image_link": token.image,
                    "unsubscribe_link": "<%a sm_group_unsubscribe_raw_url %>",
                }
                message.template_id = "d-f86ae4ff3d7342228578c9201b427cb1"
                message.asm = Asm(GroupId(17166), GroupsToDisplay([17166]))

                try:
                    sg = SendGridAPIClient(os.environ.get("SENDGRID_API_KEY"))
                    response = sg.send(message)
                    print("Sent sale notification email to " + from_profile.email)
                except Exception as e:
                    print(
                        "Error sending sale notification email to " + from_profile.email
                    )
                    print(e)

            if to_profile.email:
                message = Mail(
                    from_email=From("no-reply@quixotic.io", "Quix"),
                    to_emails=To(to_profile.email),
                )
                message.dynamic_template_data = {
                    "item_name": token.name,
                    "price": str(
                        Web3.fromWei(Web3.toWei(int(order.price), "gwei"), "ether")
                    ),
                    "currency": currency,
                    "item_link": WEBSITE_URL
                    + "/asset/"
                    + token.smart_contract.address
                    + "/"
                    + str(token.token_id),
                    "image_link": token.image,
                    "unsubscribe_link": "<%a sm_group_unsubscribe_raw_url %>",
                }
                message.template_id = "d-14feb557adfe462b80434aacb21efd74"
                message.asm = Asm(GroupId(17340), GroupsToDisplay([17340]))

                try:
                    sg = SendGridAPIClient(os.environ.get("SENDGRID_API_KEY"))
                    response = sg.send(message)
                    print("Sent purchase notification email to " + to_profile.email)
                except Exception as e:
                    print(
                        "Error sending purchase notification email to "
                        + to_profile.email
                    )
                    print(e)

        if from_profile.notifications_read:
            from_profile.notifications_read = False
            from_profile.save()
        if to_profile.notifications_read:
            to_profile.notifications_read = False
            to_profile.save()

    else:
        activity.refresh_event_type()
        print(f"Already created: {transfer_txn_id}")

    return token
