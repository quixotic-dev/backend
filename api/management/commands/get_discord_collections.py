import json

from api.models import Erc721Collection
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Return top 100 primary contracts by 7-day volume"

    def handle(self, *args, **kwargs):
        return json.dumps(
            [
                (collection.primary_contract.address, collection.primary_contract.type)
                for collection in Erc721Collection.objects.filter(
                    approved=True
                ).order_by("-volume_7d")[:100]
            ]
        )
