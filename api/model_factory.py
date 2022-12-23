import os
from datetime import datetime, timedelta, timezone

from rest_framework.exceptions import ValidationError
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Asm, From, GroupId, GroupsToDisplay, Mail, To
from web3 import Web3

from api.utils.constants import EXCHANGE_CONTRACT_V6_ADDRESS, WEBSITE_URL

from .models import (
    ActivityType,
    BlockchainState,
    CollectionOfferThreshold,
    CollectionType,
    Erc721BuyOrder,
    Erc721SellOrder,
    Erc721Token,
    Notification,
    OffChainActivity,
    PaymentToken,
    Profile,
)
from .utils.Erc721Contract import Erc721Contract


def validatePrice(price, payment_token):
    if payment_token.symbol == "OP":
        if price < 1000000000:
            raise Exception("price is too small")
        if price > 10000000000000000:
            raise Exception("price is too large")
    else:
        if price < 100000:
            raise Exception("price is too small")
        if price > 10000000000000:
            raise Exception("price is too large")


def validateDuration(start_time, end_time):
    if (end_time - start_time) < timedelta(hours=24):
        raise Exception("duration must be at least 1 day")
    if (end_time - start_time) > timedelta(days=185):
        raise Exception("duration must be less than 6 months")


def create_seaport_sell_order(
    token: Erc721Token,
    seller: str,
    start_time: datetime,
    expiration: datetime,
    price: int,  # gwei
    quantity: int,
    signature: str,
    payment_token: str,
    order_json: str,
    order_hash: str,
):

    try:
        payment_token = PaymentToken.objects.get(symbol=payment_token)
    except Exception:
        raise Exception(f"Invalid payment token: {payment_token}")

    try:
        seller, _created = Profile.objects.get_or_create(address=seller)
    except Exception as e:
        raise Exception(f"Invalid address: {seller}")

    if token.smart_contract.type == CollectionType.ERC721:
        if token.owner != seller:
            raise Exception(f"Token owner must be the same as the seller")

    validatePrice(price, payment_token)

    if not token.sell_order():
        validateDuration(start_time, expiration)
    else:
        if token.smart_contract.type == CollectionType.ERC721 and not (
            price < token.sell_order().price
        ):
            raise Exception(
                f"Price must be lower than existing listing:\nCurrent Sell Order: {token.sell_order()}\nCurrent sell order id: {token.sell_order().id}.\nCurrent Price: {token.sell_order().price}\nNew Price: {price}\nNew Order: {order_json}"
            )

    # This check works for 721s and 1155s because the isApprovedForAll function has the same signature.
    contract = Erc721Contract(token.smart_contract.address)
    assert contract.is_approved_for_all(
        seller.address, EXCHANGE_CONTRACT_V6_ADDRESS
    ), "Exchange contract is not approved to operate this token"

    sell_order = Erc721SellOrder(
        token=token,
        seller=seller,
        start_time=start_time,
        expiration=expiration,
        price=price,
        quantity=quantity,
        signature=signature,
        payment_token=payment_token,
        contract_version=6,
        order_json=str(order_json),
        message_hash=order_hash,
    )

    print(sell_order)

    sell_order.save()

    token.set_for_sale_info()

    OffChainActivity.objects.create(
        token=token,
        quantity=quantity,
        from_profile=seller,
        sell_order=sell_order,
        timestamp=datetime.now(tz=timezone.utc),
        event_type_short=ActivityType.LIST,
    )

    return sell_order


def create_seaport_buy_order(
    token: Erc721Token,
    buyer_address: str,
    start_time: datetime,
    expiration: datetime,
    price: int,  # gwei
    quantity: int,
    signature: str,
    payment_token: str,
    order_json: str,
    order_hash: str,
):

    try:
        buyer, _created = Profile.objects.get_or_create(address=buyer_address)
    except Exception as e:
        raise Exception(f"Invalid address: {buyer}")

    try:
        payment_token = PaymentToken.objects.get(symbol=payment_token)
    except Exception:
        raise Exception(f"Invalid payment token: {payment_token}")

    validatePrice(price, payment_token)

    if token.owner:
        try:
            minimum_offer = CollectionOfferThreshold.objects.get(
                profile=token.owner, collection=token.collection
            ).minimum_offer
        except Exception:
            minimum_offer = 0

        if payment_token.symbol == "OP":
            op_to_eth = BlockchainState.objects.get(key="op_eth_price").value
            if (price * float(op_to_eth)) < minimum_offer:
                raise Exception("price is too small")
        else:
            if price < minimum_offer:
                raise Exception("price is too small")

    if (expiration - start_time) < timedelta(hours=24):
        raise Exception("duration must be at least 1 day")
    if (expiration - start_time) > timedelta(days=31):
        raise Exception("duration must be less than 1 month")

    offer_count = buyer.buy_orders.filter(active=True).count()
    if offer_count >= 100:
        raise Exception(f"too many active offers from: {buyer}")

    buy_order = Erc721BuyOrder(
        token=token,
        buyer=buyer,
        start_time=start_time,
        expiration=expiration,
        price=price,
        quantity=quantity,
        signature=signature,
        payment_token=payment_token,
        contract_version=6,
        message_hash=order_hash,
        order_json=order_json,
    )

    buy_order.save()
    token.set_highest_offer()

    activty = OffChainActivity.objects.create(
        token=token,
        quantity=quantity,
        from_profile=buyer,
        buy_order=buy_order,
        timestamp=datetime.now(tz=timezone.utc),
        event_type_short=ActivityType.OFFER,
    )

    if not token.owner:
        return buy_order

    if token.owner.minimum_offer:
        if payment_token.symbol == "OP":
            op_to_eth = BlockchainState.objects.get(key="op_eth_price").value
            if (price * float(op_to_eth)) < token.owner.minimum_offer:
                return buy_order
        else:
            if price < token.owner.minimum_offer:
                return buy_order

    Notification.objects.create(
        profile=token.owner,
        token=token,
        offchain_activity_id=activty.id,
        timestamp=activty.timestamp,
    )

    if token.owner.notifications_read:
        token.owner.notifications_read = False
        token.owner.save()

    if token.owner.email:
        message = Mail(
            from_email=From("no-reply@quixotic.io", "Quix"),
            to_emails=To(token.owner.email),
        )
        message.dynamic_template_data = {
            "item_name": token.name,
            "price": str(Web3.fromWei(Web3.toWei(price, "gwei"), "ether")),
            "currency": payment_token.symbol,
            "item_link": WEBSITE_URL
            + "/asset/"
            + token.smart_contract.address
            + "/"
            + str(token.token_id),
            "image_link": token.image,
            "unsubscribe_link": "<%a sm_group_unsubscribe_raw_url %>",
        }
        message.template_id = "d-f414510a2dd54b6698e74d5ae3cba35b"
        message.asm = Asm(GroupId(17339), GroupsToDisplay([17339]))

        try:
            sg = SendGridAPIClient(os.environ.get("SENDGRID_API_KEY"))
            response = sg.send(message)
            print("Sent offer notification email to " + token.owner.email)
        except Exception as e:
            print("Error sending offer notification email to " + token.owner.email)
            print(e)

    return buy_order
