import os
from datetime import datetime, timezone
from time import sleep

from django.db import transaction
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Asm, From, GroupId, GroupsToDisplay, Mail, To
from web3 import Web3

from api.abis.erc1155_abi import erc1155_abi
from api.utils.constants import (
    ALCHEMY_API_KEY,
    NETWORK,
    REWARD_WRAPPER_ADDRESS,
    WEBSITE_URL,
)
from api.utils.constants import w3 as primary_w3
from api.utils.contract_utils import get_or_create_contract
from api.utils.process_transfer import process_fulfilled_order

from .. import models
from .ExchangeContract import exchange_addresses
from .hex_utils import to_checksum_address_from_bytes

ERC_721_SAFE_TRANSFER_TOPIC = (
    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
)
ERC_1155_SAFE_TRANSFER_TOPIC = (
    "0xc3d58168c5ae7397731d063d5bbf3d657854427343f4c083240f7aacaa2d0f62"
)
ERC_1155_SAFE_BATCH_TRANSFER_TOPIC = (
    "0x4a39dc06d4c0dbc64b70af90fd698a233a518aa5d07e595d983b8c0526c8f7fb"
)

OP_TOKEN_ADDRESS = "0x4200000000000000000000000000000000000042"


def handle_transfer_event(transfer_event, network=NETWORK):
    transfer_txn_id = transfer_event["transactionHash"]
    print(f"Processing transfer txn {transfer_txn_id}")

    contract_address = Web3.toChecksumAddress(transfer_event["address"])
    smart_contract = get_or_create_contract(
        address=contract_address,
        approved_only=True,
        save_non_nft_contract=True,
        network=network,
    )

    if not smart_contract:
        return

    if smart_contract.network.network_id != NETWORK:
        w3 = Web3(
            Web3.HTTPProvider(
                f"https://{smart_contract.network.network_id}.g.alchemy.com/v2/{ALCHEMY_API_KEY}"
            )
        )
    else:
        w3 = primary_w3

    func_hash, *other_topics = transfer_event["topics"]

    if func_hash == ERC_721_SAFE_TRANSFER_TOPIC:
        from_bytes, to_bytes, token_id_bytes = other_topics
        from_address = to_checksum_address_from_bytes(from_bytes)
        to_address = to_checksum_address_from_bytes(to_bytes)
        token_id = int(token_id_bytes, 16)
        quantity = 1

        if from_address == REWARD_WRAPPER_ADDRESS:
            # If the txn is from the Reward Wrapper, find who sent it to the Reward Wrapper
            # and set that address as the from_address
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
            print("Skipping as this transfer is to the reward contract")
            return

    elif func_hash == ERC_1155_SAFE_TRANSFER_TOPIC:
        operator_addr, from_address, to_address = (
            to_checksum_address_from_bytes(t) for t in other_topics
        )
        token_id, quantity = int(transfer_event["data"][:66], 16), int(
            transfer_event["data"][66:], 16
        )
    elif func_hash == ERC_1155_SAFE_BATCH_TRANSFER_TOPIC:
        handle_safe_batch_transfer_event(transfer_txn_id, w3=w3)
        return
    else:
        raise Exception(f"Didn't recognize transfer hash for txn: {transfer_txn_id}")

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

    try:
        full_txn = w3.eth.get_transaction(transfer_txn_id)
    except Exception:
        print(f"Transaction {transfer_txn_id} not found, retrying")
        sleep(1)
        try:
            full_txn = w3.eth.get_transaction(transfer_txn_id)
        except Exception:
            print(f"Transaction {transfer_txn_id} not found after retry")
            return

    try:
        timestamp = datetime.fromtimestamp(
            int(full_txn["l1Timestamp"], 16), timezone.utc
        )
    except Exception:
        timestamp = datetime.fromtimestamp(
            w3.eth.getBlock(full_txn["blockNumber"]).timestamp, timezone.utc
        )

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
        and "to" in full_txn
        and full_txn["to"]
        and Web3.toChecksumAddress(full_txn["to"]) in exchange_addresses
    ):
        activity = process_fulfilled_order(full_txn, activity, timestamp, w3=w3)

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
        print(f"Activity already exists: {transfer_txn_id}; Activity id {activity.id}")

    return token


def handle_safe_batch_transfer_event(txn_id, w3):
    try:
        full_txn = w3.eth.get_transaction(txn_id)
    except Exception:
        print(f"Transaction {txn_id} not found, retrying")
        sleep(1)
        try:
            full_txn = w3.eth.get_transaction(txn_id)
        except Exception:
            print(f"Transaction {txn_id} not found after retry")
            return

    try:
        timestamp = datetime.fromtimestamp(
            int(full_txn["l1Timestamp"], 16), timezone.utc
        )
    except Exception:
        timestamp = datetime.fromtimestamp(
            w3.eth.getBlock(full_txn["blockNumber"]).timestamp, timezone.utc
        )

    contract = w3.eth.contract(abi=erc1155_abi)
    receipt = w3.eth.getTransactionReceipt(txn_id)
    logs = contract.events.TransferBatch().processReceipt(receipt)
    for log_group in logs:
        if log_group["event"] != "TransferBatch":
            print(f"Received unknown event {log_group['event']} on txn {txn_id}.")
            continue

        args = log_group["args"]

        contract_address = log_group["address"]

        from_address = args["from"]
        to_address = args["to"]
        from_profile, _created = models.Profile.objects.get_or_create(
            address=from_address
        )
        to_profile, _created = models.Profile.objects.get_or_create(address=to_address)

        transfers = zip(args["ids"], args["values"])
        smart_contract = models.Contract.objects.get(address=contract_address)
        for token_id, quantity in transfers:
            try:
                token = models.Erc721Token.objects.get(
                    smart_contract=smart_contract, token_id=token_id
                )
            except models.Erc721Token.DoesNotExist:
                token = smart_contract.pull_erc1155_token(token_id)

            token.refresh_owner(from_profile=from_profile, to_profile=to_profile)
            token.soft_refresh_orders(from_profile=from_profile, to_profile=to_profile)

            try:
                (
                    activity,
                    _activity_created,
                ) = models.Erc721Activity.objects.get_or_create(
                    txn_id=txn_id,
                    token=token,
                    quantity=quantity,
                    from_profile=from_profile,
                    to_profile=to_profile,
                    timestamp=timestamp,
                )
            except Exception as e:
                print(e)
                return

            if _activity_created:
                print(f"Newly created activity: {txn_id} for token {token.token_id}")
            else:
                print(f"Activity already exists: {txn_id} for token {token.token_id}")

    print(f"Done processing {txn_id}")
