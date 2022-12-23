from api.models import Contract, Erc721Collection
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Refresh collections metadata"

    def handle(self, *args, **kwargs):
        for col in Erc721Collection.objects.filter(approved=True):
            collection = Erc721Collection.objects.get(id=col.id)
            self.stdout.write(f"Refreshing collection: {collection}")
            collection.refresh_metadata()
