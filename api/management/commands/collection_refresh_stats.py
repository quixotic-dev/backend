from api.models import Contract, Erc721Collection
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Refresh stats for collection"

    def add_arguments(self, parser):
        parser.add_argument("address", nargs=1, type=str)

    def handle(self, address, *args, **kwargs):
        smart_contract = Contract.objects.get(address=address[0])

        with transaction.atomic():
            collection = Erc721Collection.objects.select_for_update().get(
                id=smart_contract.collection.id
            )
            collection.refresh_stats()
