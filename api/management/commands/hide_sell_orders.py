from api.models import Erc721SellOrder
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Hide all active orders"

    def handle(self, *args, **kwargs):
        sell_orders = Erc721SellOrder.objects.filter(active=True)
        for order in sell_orders:
            order.active = False
            order.save()
            order.token.set_for_sale_info()
