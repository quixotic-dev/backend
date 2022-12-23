from datetime import datetime, timezone

from django.core.management.base import BaseCommand
from django.db import transaction

from api.models import Erc721BuyOrder, Erc721DutchAuction, Erc721SellOrder, Erc721Token


class Command(BaseCommand):
    help = "Refresh Expired Orders"

    def handle(self, *args, **kwargs):
        now = datetime.now(timezone.utc)

        print("Refreshing expired orders")
        sell_orders_tokens = Erc721SellOrder.objects.filter(
            active=True, expiration__lte=now
        ).values_list("token__id", flat=True)
        dutch_auctions_tokens = Erc721DutchAuction.objects.filter(
            active=True, end_time__lte=now
        ).values_list("token__id", flat=True)
        buy_orders_tokens = Erc721BuyOrder.objects.filter(
            active=True, expiration__lte=now
        ).values_list("token__id", flat=True)
        tokens = (
            list(sell_orders_tokens)
            + list(dutch_auctions_tokens)
            + list(buy_orders_tokens)
        )
        tokens = list(set(tokens))

        for token_id in tokens:
            token = Erc721Token.objects.get(id=token_id)
            token.soft_refresh_orders()
        print("Done refreshing expired orders")

        print("Refreshing dutch auctions")
        dutch_auctions = Erc721DutchAuction.objects.filter(active=True)
        for order in dutch_auctions:
            token = Erc721Token.objects.get(id=order.token.id)
            token.set_for_sale_info()
        print("Done refreshing dutch auctions")
