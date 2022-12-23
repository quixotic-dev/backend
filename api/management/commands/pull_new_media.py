from api.models import Contract, Erc721Token
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Pull media into AWS for all tokens"

    def handle(self, *args, **kwargs):
        contracts = Contract.objects.filter(collection__approved=True)

        for c in contracts:
            print(f"Pulling new media for {c} ({c.address})")

            tokens = (
                Erc721Token.objects.filter(smart_contract=c, last_media_pull=None)
                .exclude(image__isnull=True)
                .exclude(image__exact="")
                .exclude(image__startswith="https://fanbase-1.s3.amazonaws.com")
            )

            for token in tokens:
                with transaction.atomic():
                    t = Erc721Token.objects.select_for_update().get(id=token.id)
                    t.pull_media(use_existing=True)
