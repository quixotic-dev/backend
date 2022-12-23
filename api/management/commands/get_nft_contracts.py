import json

from api.models import Contract
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Return all contract addresses"

    def handle(self, *args, **kwargs):
        return json.dumps([contract.address for contract in Contract.objects.all()])
