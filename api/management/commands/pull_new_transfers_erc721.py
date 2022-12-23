import json
import os

import requests
from api.models import BlockchainState, CollectionType, Contract
from api.utils.constants import ALCHEMY_URL, NETWORK, w3
from api.utils.process_transfer_ws import handle_transfer_event
from django.core.management.base import BaseCommand
from batch_processing.tasks.token.tasks import queue_handle_transfer_event


def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


class Command(BaseCommand):
    help = "Pull new transfers for all ERC-1155 contracts"

    def handle(self, *args, **kwargs):
        block, _created = BlockchainState.objects.get_or_create(
            key="transfer_filter_block_erc721"
        )
        if _created:
            block.value = "0x1"
            block.save()

        latest_block = w3.eth.block_number
        if int(block.value, 16) > (latest_block - 1):
            return print("No new blocks to check")

        end_block = hex(latest_block)
        filter_ids = self.get_filter_ids(block.value, hex(latest_block - 1))
        for filter_id in filter_ids:
            events = self.get_events(filter_id)

            if "result" in events:
                print(f'Found {len(events["result"])} events.')
                for event in events["result"]:
                    if os.environ.get("USE_CELERY_PROCESS_TXN"):
                        txn = queue_handle_transfer_event.apply_async(
                            (event,), queue="process_txn_backfill"
                        )
                    else:
                        handle_transfer_event(event)

                print(f"Saving new block state: {latest_block}")
                block.value = hex(latest_block)
                block.save()
            elif "error" in events:
                print(events)
                try:
                    end_block = (
                        events["error"]["message"]
                        .split("[")[1]
                        .split(",")[1][:-1]
                        .strip()
                    )
                except Exception:
                    return

                filter_ids = self.get_filter_ids(block.value, end_block)
                for get_filter_id in filter_ids:
                    events = self.get_events(filter_id)

                    if "result" in events:
                        print(f'Found {len(events["result"])} events.')
                        for event in events["result"]:
                            if os.environ.get("USE_CELERY_PROCESS_TXN"):
                                txn = queue_handle_transfer_event.apply_async(
                                    (event,), queue="process_txn_backfill"
                                )
                                # print(txn)
                            else:
                                handle_transfer_event(event)

                        print(f"Saving new block state: {end_block}")
                block.value = end_block
        block.save()

    def get_filter_ids(self, block, end_block=None):
        addresses = list(
            Contract.objects.filter(
                collection__approved=True,
                type=CollectionType.ERC721,
                network__network_id=NETWORK,
            ).values_list("address", flat=True)
        )
        results = []
        for addresses_chunk in chunks(addresses, 5000):
            data = {
                "jsonrpc": "2.0",
                "method": "eth_newFilter",
                "params": [
                    {
                        "fromBlock": block,
                        "toBlock": end_block if end_block else "latest",
                        "address": addresses_chunk,
                        "topics": [
                            [
                                "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                            ]
                        ],
                    }
                ],
                "id": 1,
            }

            r = requests.post(ALCHEMY_URL, json=data)
            r_json = json.loads(r.text)
            print(r_json)
            results.append(r_json["result"])
        return results

    def get_events(self, filter_id):
        data = {
            "jsonrpc": "2.0",
            "method": "eth_getFilterLogs",
            "params": [filter_id],
            "id": 0,
        }

        r = requests.post(ALCHEMY_URL, json=data)
        r_json = json.loads(r.text)
        return r_json
