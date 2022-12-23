from api.models import Contract, Erc721Collection
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Refresh collections and contracts"

    def handle(self, *args, **kwargs):
        for col in Erc721Collection.objects.filter(approved=True):
            for con in Contract.objects.filter(collection=col, approved=True):
                contract = Contract.objects.get(id=con.id)
                self.stdout.write(f"Refreshing contract: {contract}")
                contract.refresh_contract()

            collection = Erc721Collection.objects.get(id=col.id)
            self.stdout.write(f"Refreshing collection: {collection}")
            collection.refresh_collection()
