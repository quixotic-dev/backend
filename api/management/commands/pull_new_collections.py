import json

import requests
from api.models import BlockchainState
from api.utils.constants import ALCHEMY_URL, w3
from api.utils.contract_utils import get_or_create_contract
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Pull new contracts"

    def handle(self, *args, **kwargs):
        block, _created = BlockchainState.objects.get_or_create(
            key="collection_filter_block"
        )
        if _created:
            block.value = "0x1"
            block.save()

        data = {
            "jsonrpc": "2.0",
            "method": "eth_newFilter",
            "params": [
                {
                    "fromBlock": block.value,
                    "topics": [
                        "0x8be0079c531659141344cd1fd0a4f28419497f9722a3daafe3b4186f6b6457e0",
                        "0x0000000000000000000000000000000000000000000000000000000000000000",
                    ],
                }
            ],
            "id": 0,
        }

        r = requests.post(ALCHEMY_URL, json=data)
        r_json = json.loads(r.text)

        print(r_json)

        filter_id = r_json["result"]

        data = {
            "jsonrpc": "2.0",
            "method": "eth_getFilterLogs",
            "params": [filter_id],
            "id": 0,
        }

        r = requests.post(ALCHEMY_URL, json=data)
        r_json = json.loads(r.text)

        print(r_json)

        if "result" in r_json:
            for log in r_json["result"]:
                try:
                    address = log["address"]
                except Exception:
                    return

                get_or_create_contract(address=address)

            block.value = hex(w3.eth.block_number)
            block.save()
