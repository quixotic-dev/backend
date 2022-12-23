import json

from api.models import Contract
from django.core.management.base import BaseCommand

from api.utils.constants import NETWORK


class Command(BaseCommand):
    help = "Return approved l1 contract addresses"

    def handle(self, *args, **kwargs):
        network_id = "eth-" + NETWORK[4:]
        return json.dumps(
            [
                (contract.address, contract.type)
                for contract in Contract.objects.filter(
                    collection__approved=True, network__network_id=network_id
                )
            ]
        )
