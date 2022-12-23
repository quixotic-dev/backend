from datetime import datetime, timedelta, timezone

from api.models import (
    BlockchainState,
    CollectionType,
    Erc721Activity,
    Erc721BuyOrder,
    Erc721DutchAuction,
    Erc721SellOrder,
    Erc721Token,
    Erc1155TokenOwner,
)
from api.utils.constants import NETWORK
from django.conf import settings
from django.core.cache import cache
from django.db.models import Avg, Count, Min, Q, Sum
from django.db.models.functions import Coalesce, TruncDate


def collection_supply(collection, using='default'):
    tokens = collection.erc721token_set.using(using).filter(approved=True).exclude(
        owner__address="0x0000000000000000000000000000000000000000"
    )

    if NETWORK == "opt-mainnet":
        tokens = tokens.exclude(
            owner__address="0x5a7749f83b81B301cAb5f48EB8516B986DAef23D"
        )
    elif NETWORK == "opt-goerli":
        tokens = tokens.exclude(
            owner__address="0x8DD330DdE8D9898d43b4dc840Da27A07dF91b3c9"
        )
    return tokens.count()


def collection_floor_price(collection, using='default'):
    floor_price = (
        Erc721Token.objects.using(using).filter(collection=collection, for_sale=True)
        .aggregate(Min("price_eth"))
        .get("price_eth__min")
    )
    if floor_price:
        return int(floor_price)
    else:
        return None


def collection_unique_owners(collection, using='default'):
    if (
        settings.DATABASES["default"]["ENGINE"]
        == "django.db.backends.postgresql_psycopg2"
    ):
        if collection.type == CollectionType.ERC721:
            unique_owners = Erc721Token.objects.using(using).filter(
                collection=collection, approved=True
            ).exclude(owner__address="0x0000000000000000000000000000000000000000")
        elif collection.type == CollectionType.ERC1155:
            unique_owners = Erc1155TokenOwner.objects.using(using).filter(
                token__collection=collection
            ).exclude(owner__address="0x0000000000000000000000000000000000000000")

        if NETWORK == "opt-mainnet":
            unique_owners = unique_owners.exclude(
                owner__address="0x5a7749f83b81B301cAb5f48EB8516B986DAef23D"
            )
        elif NETWORK == "opt-goerli":
            unique_owners = unique_owners.exclude(
                owner__address="0x8DD330DdE8D9898d43b4dc840Da27A07dF91b3c9"
            )

        return unique_owners.distinct("owner").count()
    else:
        return 0


def collection_listed_count(collection, using='default'):
    listed_count = Erc721Token.objects.using(using).filter(
        collection=collection, for_sale=True
    ).count()
    return listed_count


def collection_sales(collection, using='default'):
    sell_order_count = Erc721SellOrder.objects.using(using).filter(
        token__collection=collection, fulfilled=True
    ).count()
    buy_order_count = Erc721BuyOrder.objects.using(using).filter(
        token__collection=collection, fulfilled=True
    ).count()
    dutch_auction_count = Erc721DutchAuction.objects.using(using).filter(
        token__collection=collection, fulfilled=True
    ).count()

    sales = sell_order_count + buy_order_count + dutch_auction_count
    return sales


def collection_24h_sales(collection, using='default'):
    sales_key = f"collection_24h_sales__{collection.address}"
    if res := cache.get(sales_key):
        return res
    else:
        time_delta = datetime.now(timezone.utc) - timedelta(hours=24)

        sell_order_count = Erc721SellOrder.objects.using(using).filter(
            token__collection=collection, fulfilled=True, time_sold__gte=time_delta
        ).count()
        buy_order_count = Erc721BuyOrder.objects.using(using).filter(
            token__collection=collection, fulfilled=True, time_sold__gte=time_delta
        ).count()
        dutch_auction_count = Erc721DutchAuction.objects.using(using).filter(
            token__collection=collection, fulfilled=True, time_sold__gte=time_delta
        ).count()

        sales = sell_order_count + buy_order_count + dutch_auction_count
        cache.set(sales_key, sales, 60 * 30)
        return sales


def collection_Xd_sales(collection, days, using='default'):
    sales_key = f"collection_{str(days)}d_sales__{collection.address}"
    if res := cache.get(sales_key):
        return res
    else:
        time_delta = datetime.now(timezone.utc) - timedelta(days=days)

        sell_order_count = Erc721SellOrder.objects.using(using).filter(
            token__collection=collection, fulfilled=True, time_sold__gte=time_delta
        ).count()
        buy_order_count = Erc721BuyOrder.objects.using(using).filter(
            token__collection=collection, fulfilled=True, time_sold__gte=time_delta
        ).count()
        dutch_auction_count = Erc721DutchAuction.objects.using(using).filter(
            token__collection=collection, fulfilled=True, time_sold__gte=time_delta
        ).count()

        sales = sell_order_count + buy_order_count + dutch_auction_count
        cache.set(sales_key, sales, 60 * 60)
        return sales


def collection_volume(collection, using='default'):
    sell_order_volume = (
        Erc721SellOrder.objects.using(using).filter(
            token__collection=collection, fulfilled=True, payment_token__symbol="ETH"
        )
        .aggregate(Sum("price"))
        .get("price__sum")
    )
    buy_order_volume = (
        Erc721BuyOrder.objects.using(using).filter(
            token__collection=collection, fulfilled=True, payment_token__symbol="WETH"
        )
        .aggregate(Sum("price"))
        .get("price__sum")
    )
    dutch_auction_volume = (
        Erc721DutchAuction.objects.using(using).filter(
            token__collection=collection, fulfilled=True, payment_token__symbol="ETH"
        )
        .aggregate(Sum("price"))
        .get("price__sum")
    )
    volume_traded = sum(
        filter(None, [sell_order_volume, buy_order_volume, dutch_auction_volume])
    )

    try:
        op_to_eth = BlockchainState.objects.using(using).get(key="op_eth_price").value
        sell_order_volume = (
            Erc721SellOrder.objects.using(using).filter(
                token__collection=collection, fulfilled=True, payment_token__symbol="OP"
            )
            .aggregate(Sum("price"))
            .get("price__sum")
        )
        buy_order_volume = (
            Erc721BuyOrder.objects.using(using).filter(
                token__collection=collection, fulfilled=True, payment_token__symbol="OP"
            )
            .aggregate(Sum("price"))
            .get("price__sum")
        )
        dutch_auction_volume = (
            Erc721DutchAuction.objects.using(using).filter(
                token__collection=collection, fulfilled=True, payment_token__symbol="OP"
            )
            .aggregate(Sum("price"))
            .get("price__sum")
        )
        volume_traded += sum(
            filter(None, [sell_order_volume, buy_order_volume, dutch_auction_volume])
        ) * float(op_to_eth)
    except Exception as e:
        pass

    return volume_traded


def collection_24h_volume(collection, using='default'):
    volume_traded_key = f"collection_24h_volume__{collection.address}"
    if res := cache.get(volume_traded_key):
        return res
    else:
        time_delta = datetime.now(timezone.utc) - timedelta(hours=24)

        sell_order_volume = (
            Erc721SellOrder.objects.using(using).filter(
                token__collection=collection,
                fulfilled=True,
                time_sold__gte=time_delta,
                payment_token__symbol="ETH",
            )
            .aggregate(Sum("price"))
            .get("price__sum")
        )
        buy_order_volume = (
            Erc721BuyOrder.objects.using(using).filter(
                token__collection=collection,
                fulfilled=True,
                time_sold__gte=time_delta,
                payment_token__symbol="WETH",
            )
            .aggregate(Sum("price"))
            .get("price__sum")
        )
        dutch_auction_volume = (
            Erc721DutchAuction.objects.using(using).filter(
                token__collection=collection,
                fulfilled=True,
                time_sold__gte=time_delta,
                payment_token__symbol="ETH",
            )
            .aggregate(Sum("price"))
            .get("price__sum")
        )
        volume_traded = sum(
            filter(None, [sell_order_volume, buy_order_volume, dutch_auction_volume])
        )

        try:
            op_to_eth = BlockchainState.objects.using(using).get(key="op_eth_price").value
            sell_order_volume = (
                Erc721SellOrder.objects.using(using).filter(
                    token__collection=collection,
                    fulfilled=True,
                    time_sold__gte=time_delta,
                    payment_token__symbol="OP",
                )
                .aggregate(Sum("price"))
                .get("price__sum")
            )
            buy_order_volume = (
                Erc721BuyOrder.objects.using(using).filter(
                    token__collection=collection,
                    fulfilled=True,
                    time_sold__gte=time_delta,
                    payment_token__symbol="OP",
                )
                .aggregate(Sum("price"))
                .get("price__sum")
            )
            dutch_auction_volume = (
                Erc721DutchAuction.objects.using(using).filter(
                    token__collection=collection,
                    fulfilled=True,
                    time_sold__gte=time_delta,
                    payment_token__symbol="OP",
                )
                .aggregate(Sum("price"))
                .get("price__sum")
            )
            volume_traded += sum(
                filter(
                    None, [sell_order_volume, buy_order_volume, dutch_auction_volume]
                )
            ) * float(op_to_eth)
        except Exception as e:
            pass

        cache.set(volume_traded_key, volume_traded, 60 * 30)
        return volume_traded


def collection_prev_24h_volume(collection, using='default'):
    volume_traded_key = f"collection_prev_24h_volume__{collection.address}"
    if res := cache.get(volume_traded_key):
        return res
    else:
        time_delta_1 = datetime.now(timezone.utc) - timedelta(hours=48)
        time_delta_2 = datetime.now(timezone.utc) - timedelta(hours=24)

        sell_order_volume = (
            Erc721SellOrder.objects.using(using).filter(
                token__collection=collection,
                fulfilled=True,
                time_sold__gte=time_delta_1,
                time_sold__lt=time_delta_2,
                payment_token__symbol="ETH",
            )
            .aggregate(Sum("price"))
            .get("price__sum")
        )
        buy_order_volume = (
            Erc721BuyOrder.objects.using(using).filter(
                token__collection=collection,
                fulfilled=True,
                time_sold__gte=time_delta_1,
                time_sold__lt=time_delta_2,
                payment_token__symbol="WETH",
            )
            .aggregate(Sum("price"))
            .get("price__sum")
        )
        dutch_auction_volume = (
            Erc721DutchAuction.objects.using(using).filter(
                token__collection=collection,
                fulfilled=True,
                time_sold__gte=time_delta_1,
                time_sold__lt=time_delta_2,
                payment_token__symbol="ETH",
            )
            .aggregate(Sum("price"))
            .get("price__sum")
        )
        volume_traded = sum(
            filter(None, [sell_order_volume, buy_order_volume, dutch_auction_volume])
        )

        try:
            op_to_eth = BlockchainState.objects.using(using).get(key="op_eth_price").value
            sell_order_volume = (
                Erc721SellOrder.objects.using(using).filter(
                    token__collection=collection,
                    fulfilled=True,
                    time_sold__gte=time_delta_1,
                    time_sold__lt=time_delta_2,
                    payment_token__symbol="OP",
                )
                .aggregate(Sum("price"))
                .get("price__sum")
            )
            buy_order_volume = (
                Erc721BuyOrder.objects.using(using).filter(
                    token__collection=collection,
                    fulfilled=True,
                    time_sold__gte=time_delta_1,
                    time_sold__lt=time_delta_2,
                    payment_token__symbol="OP",
                )
                .aggregate(Sum("price"))
                .get("price__sum")
            )
            dutch_auction_volume = (
                Erc721DutchAuction.objects.using(using).filter(
                    token__collection=collection,
                    fulfilled=True,
                    time_sold__gte=time_delta_1,
                    time_sold__lt=time_delta_2,
                    payment_token__symbol="OP",
                )
                .aggregate(Sum("price"))
                .get("price__sum")
            )
            volume_traded += sum(
                filter(
                    None, [sell_order_volume, buy_order_volume, dutch_auction_volume]
                )
            ) * float(op_to_eth)
        except Exception as e:
            pass

        cache.set(volume_traded_key, volume_traded, 60 * 30)
        return volume_traded


def collection_24h_volume_change(collection, using='default'):
    new = collection_24h_volume(collection, using)
    old = collection_prev_24h_volume(collection, using)
    if old > 0:
        return (new - old) / old
    else:
        return None


def collection_Xd_volume(collection, days, using='default'):
    volume_traded_key = f"collection_{str(days)}d_volume__{collection.address}"
    if res := cache.get(volume_traded_key):
        return res
    else:
        time_delta = datetime.now(timezone.utc) - timedelta(days=days)

        sell_order_volume = (
            Erc721SellOrder.objects.using(using).filter(
                token__collection=collection,
                fulfilled=True,
                time_sold__gte=time_delta,
                payment_token__symbol="ETH",
            )
            .aggregate(Sum("price"))
            .get("price__sum")
        )
        buy_order_volume = (
            Erc721BuyOrder.objects.using(using).filter(
                token__collection=collection,
                fulfilled=True,
                time_sold__gte=time_delta,
                payment_token__symbol="WETH",
            )
            .aggregate(Sum("price"))
            .get("price__sum")
        )
        dutch_auction_volume = (
            Erc721DutchAuction.objects.using(using).filter(
                token__collection=collection,
                fulfilled=True,
                time_sold__gte=time_delta,
                payment_token__symbol="ETH",
            )
            .aggregate(Sum("price"))
            .get("price__sum")
        )
        volume_traded = sum(
            filter(None, [sell_order_volume, buy_order_volume, dutch_auction_volume])
        )

        try:
            op_to_eth = BlockchainState.objects.using(using).get(key="op_eth_price").value
            sell_order_volume = (
                Erc721SellOrder.objects.using(using).filter(
                    token__collection=collection,
                    fulfilled=True,
                    time_sold__gte=time_delta,
                    payment_token__symbol="OP",
                )
                .aggregate(Sum("price"))
                .get("price__sum")
            )
            buy_order_volume = (
                Erc721BuyOrder.objects.using(using).filter(
                    token__collection=collection,
                    fulfilled=True,
                    time_sold__gte=time_delta,
                    payment_token__symbol="OP",
                )
                .aggregate(Sum("price"))
                .get("price__sum")
            )
            dutch_auction_volume = (
                Erc721DutchAuction.objects.using(using).filter(
                    token__collection=collection,
                    fulfilled=True,
                    time_sold__gte=time_delta,
                    payment_token__symbol="OP",
                )
                .aggregate(Sum("price"))
                .get("price__sum")
            )
            volume_traded += sum(
                filter(
                    None, [sell_order_volume, buy_order_volume, dutch_auction_volume]
                )
            ) * float(op_to_eth)
        except Exception as e:
            pass

        cache.set(volume_traded_key, volume_traded, 60 * 60)
        return volume_traded


def collection_prev_Xd_volume(collection, days, using='default'):
    volume_traded_key = f"collection_prev_{str(days)}d_volume__{collection.address}"
    if res := cache.get(volume_traded_key):
        return res
    else:
        time_delta_1 = datetime.now(timezone.utc) - timedelta(days=days * 2)
        time_delta_2 = datetime.now(timezone.utc) - timedelta(days=days)

        sell_order_volume = (
            Erc721SellOrder.objects.using(using).filter(
                token__collection=collection,
                fulfilled=True,
                time_sold__gte=time_delta_1,
                time_sold__lt=time_delta_2,
                payment_token__symbol="ETH",
            )
            .aggregate(Sum("price"))
            .get("price__sum")
        )
        buy_order_volume = (
            Erc721BuyOrder.objects.using(using).filter(
                token__collection=collection,
                fulfilled=True,
                time_sold__gte=time_delta_1,
                time_sold__lt=time_delta_2,
                payment_token__symbol="WETH",
            )
            .aggregate(Sum("price"))
            .get("price__sum")
        )
        dutch_auction_volume = (
            Erc721DutchAuction.objects.using(using).filter(
                token__collection=collection,
                fulfilled=True,
                time_sold__gte=time_delta_1,
                time_sold__lt=time_delta_2,
                payment_token__symbol="ETH",
            )
            .aggregate(Sum("price"))
            .get("price__sum")
        )
        volume_traded = sum(
            filter(None, [sell_order_volume, buy_order_volume, dutch_auction_volume])
        )

        try:
            op_to_eth = BlockchainState.objects.using(using).get(key="op_eth_price").value
            sell_order_volume = (
                Erc721SellOrder.objects.using(using).filter(
                    token__collection=collection,
                    fulfilled=True,
                    time_sold__gte=time_delta_1,
                    time_sold__lt=time_delta_2,
                    payment_token__symbol="OP",
                )
                .aggregate(Sum("price"))
                .get("price__sum")
            )
            buy_order_volume = (
                Erc721BuyOrder.objects.using(using).filter(
                    token__collection=collection,
                    fulfilled=True,
                    time_sold__gte=time_delta_1,
                    time_sold__lt=time_delta_2,
                    payment_token__symbol="OP",
                )
                .aggregate(Sum("price"))
                .get("price__sum")
            )
            dutch_auction_volume = (
                Erc721DutchAuction.objects.using(using).filter(
                    token__collection=collection,
                    fulfilled=True,
                    time_sold__gte=time_delta_1,
                    time_sold__lt=time_delta_2,
                    payment_token__symbol="OP",
                )
                .aggregate(Sum("price"))
                .get("price__sum")
            )
            volume_traded += sum(
                filter(
                    None, [sell_order_volume, buy_order_volume, dutch_auction_volume]
                )
            ) * float(op_to_eth)
        except Exception as e:
            pass

        cache.set(volume_traded_key, volume_traded, 60 * 60)
        return volume_traded


def collection_Xd_volume_change(collection, days, using='default'):
    new = collection_Xd_volume(collection, days, using)
    old = collection_prev_Xd_volume(collection, days, using)
    if old > 0:
        return (new - old) / old
    else:
        return None


def collection_daily_stats(collection, using='default'):
    daily_stats_key = f"collection_daily_stats__{collection.address}"
    if res := cache.get(daily_stats_key):
        return res

    raw_daily_stats = (
        Erc721Activity.objects.using(using).annotate(
            coalesce_payment_token=Coalesce(
                "sell_order__payment_token__symbol",
                "buy_order__payment_token__symbol",
                "dutch_auction__payment_token__symbol",
            )
        )
        .filter(
            token__collection_id=collection.id,
            event_type_short="SA",
        )
        .filter(Q(coalesce_payment_token="ETH") | Q(coalesce_payment_token="WETH"))
        .annotate(
            date_sold=TruncDate(
                Coalesce(
                    "sell_order__time_sold",
                    "buy_order__time_sold",
                    "dutch_auction__time_sold",
                )
            )
        )
        .values("date_sold")
        .annotate(
            volume=Sum(
                Coalesce(
                    "sell_order__price", "buy_order__price", "dutch_auction__price"
                )
            )
        )
        .annotate(
            avg_price=Avg(
                Coalesce(
                    "sell_order__price", "buy_order__price", "dutch_auction__price"
                )
            )
        )
        .annotate(num_traded=Count("id"))
        .order_by("-date_sold")
    )

    i = 0
    daily_stats = []
    for stat in raw_daily_stats:
        stat_json = {
            "date": stat["date_sold"],
            "volume": int(stat["volume"]) / (10**9),
            "avg_price": int(stat["avg_price"]) / (10**9),
            "num_traded": stat["num_traded"],
        }
        daily_stats.append(stat_json)
        i += 1

    cache.set(daily_stats_key, daily_stats, 60 * 60)
    return daily_stats
