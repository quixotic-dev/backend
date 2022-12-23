from api.models import Contract
from django.core.management.base import BaseCommand

from api.utils.constants import NETWORK


class Command(BaseCommand):
    help = "Pull new tokens for all L2 contracts"

    def handle(self, *args, **kwargs):
        contracts = Contract.objects.filter(
            collection__approved=True, network__network_id=NETWORK
        )

        for c in contracts:
            print(f"Pulling new tokens for {c} ({c.address})")
            c.pull_new_tokens()
