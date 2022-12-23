import json
import os
from api.utils.constants import NETWORK

from api.utils.process_transfer_ws import handle_transfer_event
from batch_processing.tasks.token.tasks import process_erc721_transfer_event
from django.core.management.base import BaseCommand

erc721_safe_transfer_from_topic = (
    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
)


class Command(BaseCommand):
    help = "Update the backend system to take into account a particular txn."

    def add_arguments(self, parser):
        parser.add_argument("transfer_txn_ids", nargs=1, type=str)

    def handle(self, transfer_txn_ids, *args, **kwargs):
        network = "eth-" + NETWORK[4:]
        json_event = json.loads(transfer_txn_ids[0])
        is_erc721_transfer = json_event["topics"][0] == erc721_safe_transfer_from_topic
        if os.environ.get("USE_CELERY_PROCESS_TXN") and is_erc721_transfer:
            address = json_event["address"]
            topics = tuple(json_event["topics"])
            transactionHash = json_event["transactionHash"]
            process_erc721_transfer_event.apply_async(
                (transactionHash, address, topics, network), queue="process_txn"
            )
        else:
            handle_transfer_event(json_event, network=network)
