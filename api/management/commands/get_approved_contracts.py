import json

from api.models import Contract
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Return approved contract addresses"

    def handle(self, *args, **kwargs):
        return json.dumps(
            [
                (contract.address, contract.type)
                for contract in Contract.objects.filter(collection__approved=True)
            ]
        )
