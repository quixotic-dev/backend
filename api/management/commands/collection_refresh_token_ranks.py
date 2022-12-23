from django.core.management.base import BaseCommand
from django.db import transaction

from api.models import Contract, Erc721Collection, Erc721Token


class Command(BaseCommand):
    help = "Refresh token ranks for collection"

    def add_arguments(self, parser):
        parser.add_argument("address", nargs=1, type=str)

    def handle(self, address, *args, **kwargs):
        smart_contract = Contract.objects.get(address=address[0])
        collection = Erc721Collection.objects.get(id=smart_contract.collection.id)
        tokens = Erc721Token.objects.filter(collection=collection).order_by("id")
        print(f"Refreshing ranks for {len(tokens)} tokens in {collection}")

        i = 0
        for t in tokens:
            with transaction.atomic():
                token = Erc721Token.objects.select_for_update().get(id=t.id)
                token.refresh_rank()

            if i % 100 == 0:
                print(f"====> {i}", t)
            i += 1

        print(f"Finished refreshing ranks for {collection}")
