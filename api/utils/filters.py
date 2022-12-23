import functools
import os

from api.models import Erc721Activity, Erc721Token, OffChainActivity
from api.utils.constants import NETWORK, NULL_PROFILE_INTERNAL_ID, BRIDGE_PROFILE_INTERNAL_ID
from django.db.models import F, PositiveBigIntegerField, Q
from django.db.models.functions import Cast, Coalesce

HARD_PAYLOAD_LIMIT = 9999
HARD_ACTIVITY_PAYLOAD_LIMIT = 9999


def collection_token_filters(
        attribute_filters,
        sorters,
        availability,
        price,
        payment_token,
        chains,
        collection_id,
        intersect_attributes=False,
        is_erc721_collection=True
):
    def fmat(value):
        assert ";" not in value
        value = value.replace("'", "''")
        value = value.replace("%", "%%")
        return value

    # Get all tokens owned from collection, exluding burnt tokens
    if os.environ.get("DATABASE_FOLLOWER_CONNECTION_POOL_URL"):
        tokens = Erc721Token.objects.using("follower")
    else:
        tokens = Erc721Token.objects

    tokens = tokens.filter(
        collection_id=collection_id,
        approved=True,
    )

    if is_erc721_collection:
        if NULL_PROFILE_INTERNAL_ID:
            tokens = tokens.exclude(owner__id=NULL_PROFILE_INTERNAL_ID)
        else:
            tokens = tokens.exclude(owner__address="0x0000000000000000000000000000000000000000")
    else:
        tokens = tokens.exclude(erc1155tokenowner__owner__address="0x0000000000000000000000000000000000000000")


    if BRIDGE_PROFILE_INTERNAL_ID:
        tokens = tokens.exclude(
            owner__id=BRIDGE_PROFILE_INTERNAL_ID
        )

    # Filter by attribute
    if attribute_filters:
        if intersect_attributes:
            for attribute in attribute_filters:
                trait, value = attribute.split(":")
                tokens = tokens.filter(
                    erc721tokenattribute__trait_type=trait,
                    erc721tokenattribute__value=value,
                )
        else:
            filter_fn = functools.reduce(
                lambda q, f: q
                             | Q(
                    erc721tokenattribute__trait_type=f.split(":")[0],
                    erc721tokenattribute__value=f.split(":")[1],
                ),
                attribute_filters,
                Q(),
            )
            tokens = tokens.filter(filter_fn)

    # Filter by marketplace availability
    if availability == "forSale":
        tokens = tokens.filter(for_sale=True)
    elif availability == "hasOffers":
        tokens = tokens.exclude(highest_offer__isnull=True)
    elif availability == "notListed":
        tokens = tokens.filter(for_sale=False)

    # Filter by price
    if price:
        price_tags = price.split(":")
        if len(price_tags) == 1:
            tokens = tokens.filter(price__gte=fmat(price_tags[0]))
        elif len(price_tags) == 2:
            tokens = tokens.filter(
                price__gte=fmat(price_tags[0]),
                price__lte=fmat(price_tags[1]),
            )

    # Filter by payment token
    if payment_token:
        if payment_token == "ETH":
            tokens = tokens.filter(
                Q(payment_token__symbol="ETH") | Q(payment_token__symbol="WETH")
            )

        else:
            tokens = tokens.filter(payment_token__symbol=fmat(payment_token))

    if chains:
        tokens = tokens.filter(smart_contract__network__network__in=chains)

    # Sort remaining tokens
    if len(sorters) > 0:
        # Only use first sort tag
        sort_tag = sorters[0]
        field, order = sort_tag.split(":")

        # Ensure sort tag has valid order
        assert (
                order.lower() == "asc" or order.lower() == "desc"
        ), "Not a valid filter tag"

        if field == "price":
            field = "price_eth"
        elif field == "highest_offer":
            field = "highest_offer_eth"
        elif field == "token_id":
            tokens = tokens.annotate(
                token_id_int=Cast("token_id", PositiveBigIntegerField())
            )
            field = "token_id_int"

        sort_fn = getattr(F(field), order.lower())
        if field == "rank" or field == "token_id_int" or field == "highest_offer_eth":
            tokens = tokens.order_by(sort_fn(nulls_last=True))
        else:
            tokens = tokens.order_by(
                "-for_sale",
                sort_fn(nulls_last=True),
            )

    return tokens


def collection_activity_filters(
        event_types,
        sorters,
        attribute_filters,
        price,
        payment_token,
        chains,
        collection_id,
        intersect_attributes=False,
):
    def fmat(value):
        assert ";" not in value
        value = value.replace("'", "''")
        value = value.replace("%", "%%")
        return value

    if os.environ.get("DATABASE_FOLLOWER_CONNECTION_POOL_URL"):
        on_chain_activity = (
            Erc721Activity.objects.using("follower")
                .filter(
                token__approved=True,
                token__collection__approved=True,
                token__collection_id=collection_id,
            )
                .annotate(
                coalesce_price=Coalesce(
                    "sell_order__price", "buy_order__price", "dutch_auction__price"
                )
            )
                .annotate(
                coalesce_payment_token=Coalesce(
                    "sell_order__payment_token__symbol",
                    "buy_order__payment_token__symbol",
                    "dutch_auction__payment_token__symbol",
                )
            )
        )
        off_chain_activity = (
            OffChainActivity.objects.using("follower")
                .filter(
                token__approved=True,
                token__collection__approved=True,
                token__collection_id=collection_id,
            )
                .annotate(
                coalesce_price=Coalesce(
                    "sell_order__price", "buy_order__price", "dutch_auction__price"
                )
            )
                .annotate(
                coalesce_payment_token=Coalesce(
                    "sell_order__payment_token__symbol",
                    "buy_order__payment_token__symbol",
                    "dutch_auction__payment_token__symbol",
                )
            )
        )
    else:
        on_chain_activity = (
            Erc721Activity.objects.filter(
                token__approved=True,
                token__collection__approved=True,
                token__collection_id=collection_id,
            )
                .annotate(
                coalesce_price=Coalesce(
                    "sell_order__price", "buy_order__price", "dutch_auction__price"
                )
            )
                .annotate(
                coalesce_payment_token=Coalesce(
                    "sell_order__payment_token__symbol",
                    "buy_order__payment_token__symbol",
                    "dutch_auction__payment_token__symbol",
                )
            )
        )
        off_chain_activity = (
            OffChainActivity.objects.filter(
                token__approved=True,
                token__collection__approved=True,
                token__collection_id=collection_id,
            )
                .annotate(
                coalesce_price=Coalesce(
                    "sell_order__price", "buy_order__price", "dutch_auction__price"
                )
            )
                .annotate(
                coalesce_payment_token=Coalesce(
                    "sell_order__payment_token__symbol",
                    "buy_order__payment_token__symbol",
                    "dutch_auction__payment_token__symbol",
                )
            )
        )

    if len(event_types) > 0:
        on_chain_activity = on_chain_activity.filter(event_type_short__in=event_types)
        off_chain_activity = off_chain_activity.filter(event_type_short__in=event_types)

    # Filter by price
    if price:
        price_tags = price.split(":")
        if len(price_tags) == 1:
            on_chain_activity = on_chain_activity.filter(
                Q(coalesce_price__gte=fmat(price_tags[0]))
            )
            off_chain_activity = off_chain_activity.filter(
                Q(coalesce_price__gte=fmat(price_tags[0]))
            )
        elif len(price_tags) == 2:
            on_chain_activity = on_chain_activity.filter(
                Q(
                    coalesce_price__gte=fmat(price_tags[0]),
                    coalesce_price__lte=fmat(price_tags[1]),
                )
            )
            off_chain_activity = off_chain_activity.filter(
                Q(
                    coalesce_price__gte=fmat(price_tags[0]),
                    coalesce_price__lte=fmat(price_tags[1]),
                )
            )

    # Filter by payment token
    if payment_token:
        if payment_token == "ETH":
            on_chain_activity = on_chain_activity.filter(
                Q(coalesce_payment_token="ETH") | Q(coalesce_payment_token="WETH")
            )
            off_chain_activity = off_chain_activity.filter(
                Q(coalesce_payment_token="ETH") | Q(coalesce_payment_token="WETH")
            )
        else:
            on_chain_activity = on_chain_activity.filter(
                Q(coalesce_payment_token=fmat(payment_token))
            )
            off_chain_activity = off_chain_activity.filter(
                Q(coalesce_payment_token=fmat(payment_token))
            )

    # Filter by attribute
    if attribute_filters:
        if intersect_attributes:
            for attribute in attribute_filters:
                trait, value = attribute.split(":")
                on_chain_activity = on_chain_activity.filter(
                    token__erc721tokenattribute__trait_type=trait,
                    token__erc721tokenattribute__value=value,
                )
                off_chain_activity = off_chain_activity.filter(
                    token__erc721tokenattribute__trait_type=trait,
                    token__erc721tokenattribute__value=value,
                )
        else:
            filter_fn = functools.reduce(
                lambda q, f: q
                             | Q(
                    token__erc721tokenattribute__trait_type=f.split(":")[0],
                    token__erc721tokenattribute__value=f.split(":")[1],
                ),
                attribute_filters,
                Q(),
            )
            on_chain_activity = on_chain_activity.filter(filter_fn)
            off_chain_activity = off_chain_activity.filter(filter_fn)

    if chains:
        on_chain_activity = on_chain_activity.filter(
            token__smart_contract__network__network__in=chains
        )
        off_chain_activity = off_chain_activity.filter(
            token__smart_contract__network__network__in=chains
        )

    activity = on_chain_activity.union(off_chain_activity)

    # Sort remaining tokens
    if len(sorters) > 0:
        # Only use first sort tag
        sort_tag = sorters[0]
        field, order = sort_tag.split(":")

        # Ensure sort tag has valid order
        assert (
                order.lower() == "asc" or order.lower() == "desc"
        ), "Not a valid filter tag"

        if field == "price":
            field = "coalesce_price"

        sort_fn = getattr(F(field), order.lower())

        activity = activity.order_by(
            sort_fn(nulls_last=True),
            "-timestamp",
        )

    return activity


def explore_token_filters(collections, sorters, availability, price, payment_token):
    def fmat(value):
        assert ";" not in value
        value = value.replace("'", "''")
        value = value.replace("%", "%%")
        return value

    collection_where_clauses = [
        f"col.address = '{fmat(address)}'" for address in collections
    ]
    collection_where_clause = (
        "and (" + " or ".join(collection_where_clauses) + ")"
        if len(collection_where_clauses) > 0
        else ""
    )

    sort_tags = []
    sorters = ["for_sale:desc"] + sorters
    for sort_tag in sorters:
        split_tag = sort_tag.split(":")
        sort_tags.append(split_tag)
        assert (
                split_tag[1].lower() == "asc" or split_tag[1].lower() == "desc"
        ), "Not a valid filter tag"
        if (
                split_tag[0] == "rank"
                or split_tag[0] == "id"
                or split_tag[0] == "highest_offer"
        ):
            sort_tags.pop(0)

    sort_clauses = []
    for field, ordering in sort_tags:
        if field == "price":
            sort_clauses.append(f"tok.price_eth {fmat(ordering)} nulls last")
        elif field == "highest_offer":
            sort_clauses.append(f"tok.highest_offer_eth {fmat(ordering)} nulls last")
        else:
            sort_clauses.append(f"tok.{fmat(field)} {fmat(ordering)} nulls last")
    sort_clause = ("order by " + ",".join(sort_clauses)) if sort_clauses else ""

    availability_where_clause = ""
    if availability == "forSale":
        availability_where_clause = "and tok.for_sale=True"
    elif availability == "hasOffers":
        availability_where_clause = "and tok.highest_offer is not null"
    elif availability == "notListed":
        availability_where_clause = "and tok.for_sale=False"

    price_tags = []
    price_where_clause = ""
    if price:
        price_tags = price.split(":")
        if len(price_tags) == 1:
            price_where_clause = (
                f"and tok.for_sale=True and tok.price >= {fmat(price_tags[0])}"
            )
        elif len(price_tags) == 2:
            price_where_clause = f"and tok.for_sale=True and tok.price >= {fmat(price_tags[0])} and tok.price <= {fmat(price_tags[1])}"

    payment_token_where_clause = ""
    if payment_token:
        if payment_token == "ETH":
            payment_token_where_clause = (
                f"and (pt.symbol = 'ETH' or pt.symbol = 'WETH')"
            )
        else:
            payment_token_where_clause = f"and pt.symbol = '{fmat(payment_token)}'"

    raw_sql = f"""
    select tok.id from api_erc721token tok
    join api_erc721collection col on col.id = tok.collection_id
    left join api_paymenttoken pt on tok.payment_token_id = pt.id
    where tok.approved = True and col.approved = True
    and col.is_spam = False and col.delisted = False
    {collection_where_clause}
    {availability_where_clause}
    {price_where_clause}
    {payment_token_where_clause}
    {sort_clause}
    limit {HARD_PAYLOAD_LIMIT}
    """

    if os.environ.get("DATABASE_FOLLOWER_CONNECTION_POOL_URL"):
        tokens = Erc721Token.objects.using("follower").raw(raw_sql)
    else:
        tokens = Erc721Token.objects.raw(raw_sql)
    return tokens


def explore_activity_filters(collections, sorters, event_types, price, payment_token):
    def fmat(value):
        assert ";" not in value
        value = value.replace("'", "''")
        value = value.replace("%", "%%")
        return value

    collection_where_clauses = [
        f"col.address = '{fmat(address)}'" for address in collections
    ]
    collection_where_clause = (
        "and (" + " or ".join(collection_where_clauses) + ")"
        if len(collection_where_clauses) > 0
        else ""
    )

    event_type_where_clauses = [
        f"act.event_type_short = '{fmat(event)}'" for event in event_types
    ]
    event_type_where_clause = (
        "and (" + " or ".join(event_type_where_clauses) + ")"
        if len(event_type_where_clauses) > 0
        else ""
    )

    sort_tags = []
    sorters = sorters + ["timestamp:desc"]
    for sort_tag in sorters:
        split_tag = sort_tag.split(":")
        sort_tags.append(split_tag)
        assert (
                split_tag[1].lower() == "asc" or split_tag[1].lower() == "desc"
        ), "Not a valid filter tag"

    sort_clauses = []
    for field, ordering in sort_tags:
        if field == "price":
            sort_clauses.append(f"unified_price {fmat(ordering)} nulls last")
        else:
            sort_clauses.append(f"act.{fmat(field)} {fmat(ordering)} nulls last")
    sort_clause = ("order by " + ",".join(sort_clauses)) if sort_clauses else ""

    price_tags = []
    price_where_clause = ""
    if price:
        price_tags = price.split(":")
        if len(price_tags) == 1:
            price_where_clause = (
                f"and coalesce(so.price, bo.price, da.price) >= {fmat(price_tags[0])}"
            )
        elif len(price_tags) == 2:
            price_where_clause = f"and coalesce(so.price, bo.price, da.price) >= {fmat(price_tags[0])} and coalesce(so.price, bo.price, da.price) <= {fmat(price_tags[1])}"

    payment_token_where_clause = ""
    if payment_token:
        if payment_token == "ETH":
            payment_token_where_clause = (
                f"and (pt.symbol = 'ETH' or pt.symbol = 'WETH')"
            )
        else:
            payment_token_where_clause = f"and pt.symbol = '{fmat(payment_token)}'"

    raw_sql = f"""
    select act.*, coalesce(so.price, bo.price, da.price) as unified_price from
    (select id, txn_id, token_id, sell_order_id, dutch_auction_id, buy_order_id, from_profile_id, to_profile_id, timestamp, event_type_short from api_erc721activity
    union all
    select id, Null, token_id, sell_order_id, dutch_auction_id, buy_order_id, from_profile_id, to_profile_id, timestamp, event_type_short from api_offchainactivity) act
    join api_erc721token tok on act.token_id = tok.id
    join api_erc721collection col on col.id = tok.collection_id
    left join api_erc721sellorder so on act.sell_order_id = so.id
    left join api_erc721buyorder bo on act.buy_order_id = bo.id
    left join api_erc721dutchauction da on act.dutch_auction_id = da.id
    left join api_paymenttoken pt on (so.payment_token_id = pt.id or da.payment_token_id = pt.id or bo.payment_token_id = pt.id)
    where tok.approved = True and col.approved = True
    {collection_where_clause}
    {price_where_clause}
    {payment_token_where_clause}
    {event_type_where_clause}
    {sort_clause}
    limit {HARD_ACTIVITY_PAYLOAD_LIMIT}
    """

    if os.environ.get("DATABASE_FOLLOWER_CONNECTION_POOL_URL"):
        activity = Erc721Activity.objects.using("follower").raw(raw_sql)
    else:
        activity = Erc721Activity.objects.raw(raw_sql)
    return activity


def profile_token_filters(
        collections,
        sorters,
        availability,
        price,
        payment_token,
        chains,
        profile_id,
        pull_erc721s=True,
        pull_erc1155s=True,
):
    def fmat(value):
        assert ";" not in value
        value = value.replace("'", "''")
        value = value.replace("%", "%%")
        return value

    # Get all non-hidden tokens owned by user
    if os.environ.get("DATABASE_FOLLOWER_CONNECTION_POOL_URL"):
        tokens = Erc721Token.objects.using("follower")
    else:
        tokens = Erc721Token.objects

    q_filters = Q()
    if pull_erc721s:
        q_filters = q_filters | Q(owner_id=profile_id) | Q(pending_owner=profile_id)

    if pull_erc1155s:
        q_filters = q_filters | Q(erc1155tokenowner__owner_id=profile_id)

    tokens = tokens.filter(q_filters, approved=True, collection__approved=True).exclude(
        hiddentoken__user_id=profile_id
    )

    # Filter by collection
    if len(collections) > 0:
        tokens = tokens.filter(collection__address__in=collections)

    # Filter by marketplace availability
    if availability == "forSale":
        tokens = tokens.filter(for_sale=True)
    elif availability == "hasOffers":
        tokens = tokens.exclude(highest_offer__isnull=True)
    elif availability == "notListed":
        tokens = tokens.filter(for_sale=False)

    # Filter by price
    if price:
        price_tags = price.split(":")
        if len(price_tags) == 1:
            tokens = tokens.filter(price__gte=fmat(price_tags[0]))
        elif len(price_tags) == 2:
            tokens = tokens.filter(
                price__gte=fmat(price_tags[0]),
                price__lte=fmat(price_tags[1]),
            )

    # Filter by payment token
    if payment_token:
        if payment_token == "ETH":
            tokens = tokens.filter(
                Q(payment_token__symbol="ETH") | Q(payment_token__symbol="WETH")
            )

        else:
            tokens = tokens.filter(payment_token__symbol=fmat(payment_token))

    if chains:
        tokens = tokens.filter(smart_contract__network__network__in=chains)

    # Sort remaining tokens
    if len(sorters) > 0:
        # Only use first sort tag
        sort_tag = sorters[0]
        field, order = sort_tag.split(":")

        # Ensure sort tag has valid order
        assert (
                order.lower() == "asc" or order.lower() == "desc"
        ), "Not a valid filter tag"

        if field == "price":
            field = "price_eth"
        elif field == "highest_offer":
            field = "highest_offer_eth"

        sort_fn = getattr(F(field), order.lower())

        if field == "rank" or field == "id" or field == "highest_offer_eth":
            tokens = tokens.order_by(sort_fn(nulls_last=True), "-collection_id", "-id")
        else:
            tokens = tokens.order_by(
                "-for_sale",
                sort_fn(nulls_last=True),
                "-collection_id",
                "-id",
            )

    return tokens


def profile_activity_filters(
        collections, sorters, event_types, price, payment_token, chains, profile_id
):
    def fmat(value):
        assert ";" not in value
        value = value.replace("'", "''")
        value = value.replace("%", "%%")
        return value

    if os.environ.get("DATABASE_FOLLOWER_CONNECTION_POOL_URL"):
        on_chain_activity = (
            Erc721Activity.objects.using("follower")
                .filter(
                (Q(from_profile_id=profile_id) | Q(to_profile_id=profile_id)),
                token__approved=True,
                token__collection__approved=True,
            )
                .annotate(
                coalesce_price=Coalesce(
                    "sell_order__price", "buy_order__price", "dutch_auction__price"
                )
            )
                .annotate(
                coalesce_payment_token=Coalesce(
                    "sell_order__payment_token__symbol",
                    "buy_order__payment_token__symbol",
                    "dutch_auction__payment_token__symbol",
                )
            )
        )
        off_chain_activity = (
            OffChainActivity.objects.using("follower")
                .filter(
                (Q(from_profile_id=profile_id) | Q(to_profile_id=profile_id)),
                token__approved=True,
                token__collection__approved=True,
            )
                .annotate(
                coalesce_price=Coalesce(
                    "sell_order__price", "buy_order__price", "dutch_auction__price"
                )
            )
                .annotate(
                coalesce_payment_token=Coalesce(
                    "sell_order__payment_token__symbol",
                    "buy_order__payment_token__symbol",
                    "dutch_auction__payment_token__symbol",
                )
            )
        )
    else:
        on_chain_activity = (
            Erc721Activity.objects.filter(
                (Q(from_profile_id=profile_id) | Q(to_profile_id=profile_id)),
                token__approved=True,
                token__collection__approved=True,
            )
                .annotate(
                coalesce_price=Coalesce(
                    "sell_order__price", "buy_order__price", "dutch_auction__price"
                )
            )
                .annotate(
                coalesce_payment_token=Coalesce(
                    "sell_order__payment_token__symbol",
                    "buy_order__payment_token__symbol",
                    "dutch_auction__payment_token__symbol",
                )
            )
        )
        off_chain_activity = (
            OffChainActivity.objects.filter(
                (Q(from_profile_id=profile_id) | Q(to_profile_id=profile_id)),
                token__approved=True,
                token__collection__approved=True,
            )
                .annotate(
                coalesce_price=Coalesce(
                    "sell_order__price", "buy_order__price", "dutch_auction__price"
                )
            )
                .annotate(
                coalesce_payment_token=Coalesce(
                    "sell_order__payment_token__symbol",
                    "buy_order__payment_token__symbol",
                    "dutch_auction__payment_token__symbol",
                )
            )
        )

    # Filter by collection
    if len(collections) > 0:
        on_chain_activity = on_chain_activity.filter(
            token__collection__address__in=collections
        )
        off_chain_activity = off_chain_activity.filter(
            token__collection__address__in=collections
        )

    # Filter by event type
    if len(event_types) > 0:
        on_chain_activity = on_chain_activity.filter(event_type_short__in=event_types)
        off_chain_activity = off_chain_activity.filter(event_type_short__in=event_types)

    # Filter by price
    if price:
        price_tags = price.split(":")
        if len(price_tags) == 1:
            on_chain_activity = on_chain_activity.filter(
                Q(coalesce_price__gte=fmat(price_tags[0]))
            )
            off_chain_activity = off_chain_activity.filter(
                Q(coalesce_price__gte=fmat(price_tags[0]))
            )
        elif len(price_tags) == 2:
            on_chain_activity = on_chain_activity.filter(
                Q(
                    coalesce_price__gte=fmat(price_tags[0]),
                    coalesce_price__lte=fmat(price_tags[1]),
                )
            )
            off_chain_activity = off_chain_activity.filter(
                Q(
                    coalesce_price__gte=fmat(price_tags[0]),
                    coalesce_price__lte=fmat(price_tags[1]),
                )
            )

    # Filter by payment token
    if payment_token:
        if payment_token == "ETH":
            on_chain_activity = on_chain_activity.filter(
                Q(coalesce_payment_token="ETH") | Q(coalesce_payment_token="WETH")
            )
            off_chain_activity = off_chain_activity.filter(
                Q(coalesce_payment_token="ETH") | Q(coalesce_payment_token="WETH")
            )
        else:
            on_chain_activity = on_chain_activity.filter(
                Q(coalesce_payment_token=fmat(payment_token))
            )
            off_chain_activity = off_chain_activity.filter(
                Q(coalesce_payment_token=fmat(payment_token))
            )

    if chains:
        on_chain_activity = on_chain_activity.filter(
            token__smart_contract__network__network__in=chains
        )
        off_chain_activity = off_chain_activity.filter(
            token__smart_contract__network__network__in=chains
        )

    activity = on_chain_activity.union(off_chain_activity)

    # Sort remaining tokens
    if len(sorters) > 0:
        # Only use first sort tag
        sort_tag = sorters[0]
        field, order = sort_tag.split(":")

        # Ensure sort tag has valid order
        assert (
                order.lower() == "asc" or order.lower() == "desc"
        ), "Not a valid filter tag"

        if field == "price":
            field = "coalesce_price"

        sort_fn = getattr(F(field), order.lower())

        activity = activity.order_by(
            sort_fn(nulls_last=True),
            "-timestamp",
        )

    return activity
