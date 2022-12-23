import json

from api.utils.contract_utils import get_or_create_contract
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Add newly deployed contract to backend"

    def add_arguments(self, parser):
        parser.add_argument("event", nargs=1, type=str)

    def handle(self, event, *args, **kwargs):
        json_event = json.loads(event[0])

        try:
            address = json_event["address"]
        except Exception:
            return

        get_or_create_contract(address=address)
