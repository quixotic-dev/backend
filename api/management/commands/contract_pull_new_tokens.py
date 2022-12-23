from api.models import Contract
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Pull new tokens for contract"

    def add_arguments(self, parser):
        parser.add_argument("address", nargs=1, type=str)

    def handle(self, address, *args, **kwargs):
        smart_contract = Contract.objects.get(address=address[0])
        smart_contract.pull_new_tokens()
