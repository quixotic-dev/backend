import json

from api.models import NonNFTContract
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Return non-NFT contract addresses"

    def handle(self, *args, **kwargs):
        return json.dumps(
            [
                contract.address
                for contract in NonNFTContract.objects.filter(network_id=1)
            ]
        )
