import json
from time import sleep

import requests
from api.models import BlockchainState
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Pull current ETH price"

    def handle(self, *args, **kwargs):
        # Update ETH -> USD conversion
        try:
            eth_usd_price, _created = BlockchainState.objects.get_or_create(
                key="eth_usd_price"
            )

            url = "https://api.coinbase.com/v2/exchange-rates?currency=ETH"
            r = requests.get(url)
            rates = json.loads(r.text)
            usd = rates["data"]["rates"]["USD"]

            eth_usd_price.value = round(float(usd), 2)
            eth_usd_price.save()
        except Exception as e:
            print(e)
            return

        # Update ETH -> OP conversions
        try:
            eth_op_price, _created = BlockchainState.objects.get_or_create(
                key="eth_op_price"
            )
            op = rates["data"]["rates"]["OP"]
            eth_op_price.value = round(float(op), 4)
            eth_op_price.save()
        except Exception as e:
            print(e)
            return

        sleep(1)

        # Update OP -> USD/ETH conversions
        try:
            op_usd_price, _created = BlockchainState.objects.get_or_create(
                key="op_usd_price"
            )
            op_eth_price, _created = BlockchainState.objects.get_or_create(
                key="op_eth_price"
            )

            url = "https://api.coinbase.com/v2/exchange-rates?currency=OP"
            r = requests.get(url)
            rates = json.loads(r.text)
            usd = rates["data"]["rates"]["USD"]
            eth = rates["data"]["rates"]["ETH"]

            op_usd_price.value = round(float(usd), 2)
            op_usd_price.save()

            op_eth_price.value = round(float(eth), 8)
            op_eth_price.save()
        except Exception:
            pass
