from api.models import CollectionType, Contract, Erc721Token
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Refresh tokens for contract"

    def add_arguments(self, parser):
        parser.add_argument("address", nargs=1, type=str)

    def handle(self, address, *args, **kwargs):
        smart_contract = Contract.objects.get(address=address[0])
        tokens = Erc721Token.objects.filter(smart_contract=smart_contract)
        print(f"Refreshing {len(tokens)} tokens in {smart_contract}")

        i = 0
        for t in tokens:
            with transaction.atomic():
                token = Erc721Token.objects.select_for_update().get(id=t.id)
                token.refresh_token()

                if smart_contract.type == CollectionType.ERC1155:
                    token.refresh_activity_history(hard_pull=True)

            if i % 100 == 0:
                print(f"====> {i}", t)
            i += 1

        print(f"Finished refreshing tokens for {smart_contract}")
