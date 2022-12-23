from api.models import CollectionType, Contract, Erc721Token
from api.utils.constants import NETWORK
from api.utils.process_transfer_ws import handle_transfer_event
from celery import shared_task
from django.db import transaction
from django.core.cache import cache

from api.utils.constants import IS_CELERY_PROCESSING_TXNS
from ...models import StaleOwnerRecord
from ...utils.txn_utils import get_transfer_logs


@shared_task(rate_limit="12/s")
def refresh_token(internal_id, retries=0):
    """
    Use internal id not token id
    """

    token = Erc721Token.objects.get(id=internal_id)
    if token.collection.type == CollectionType.ERC1155:
        token.refresh_token()
        return True
    else:
        with transaction.atomic():
            token = Erc721Token.objects.select_for_update().get(id=internal_id)
            token.refresh_token()

    # if retries and not token.owner:
    #     refresh_token.apply_async(
    #         (token.id, retries - 1), queue="refresh_token", countdown=10
    #     )  # wait 10 seconds before running retry

    return True


@shared_task(rate_limit="4/s")
def pull_new_media_for_token(internal_id):
    """
    Use internal id not token id
    """
    raise Exception("NotImplemented")
    # token = Erc721Token.objects.get(id=internal_id)
    # token.pull_media(use_existing=True)
    # return True


@shared_task(bind=True)
def refresh_token_owner(self, internal_id, batch_job_id=None):
    token = Erc721Token.objects.get(id=internal_id)
    cur_owner = token.owner
    token.refresh_owner(should_save=True)
    updated_owner = token.owner
    owner_changed = cur_owner != updated_owner
    if owner_changed:
        StaleOwnerRecord.objects.create(
            batch_job_id=batch_job_id,
            celery_task_id=self.request.id,
            old_owner=cur_owner,
            new_owner=updated_owner,
        )

    return 1 if owner_changed else 0


@shared_task(bind=True)
def refresh_1155_token_owner(self, internal_id, batch_job_id=None):
    token = Erc721Token.objects.get(id=internal_id)
    token.refresh_erc1155_owners()
    return


@shared_task(rate_limit="64/s")
def process_erc721_transfer_event(transactionHash, address, topics, network=NETWORK):
    cache.set(IS_CELERY_PROCESSING_TXNS, True, 60 * 10)  # Cache for 10 minutes
    json_event = {
        "transactionHash": transactionHash,
        "address": address,
        "topics": topics,
    }
    token = handle_transfer_event(json_event, network=network)
    if token:
        return token.id
    else:
        print("This is likely an ERC20.")


@shared_task(rate_limit="64/s")
def queue_handle_transfer_event(json_event, network=NETWORK):
    cache.set(IS_CELERY_PROCESSING_TXNS, True, 60 * 10)  # Cache for 10 minutes
    token = handle_transfer_event(json_event, network=network)
    if token:
        return token.id
    else:
        print("This is likely an ERC20.")


@shared_task
def process_all_transfers_in_txn(transfer_txn_id):
    """
    Remember a txn can have multiple transfer events. This is very common in batch minting.
    """
    transfer_events = get_transfer_logs(transfer_txn_id)
    for transfer_event in transfer_events:
        transactionHash = transfer_event["transactionHash"]
        address = transfer_event["address"]
        topics = tuple(transfer_event["topics"])
        process_erc721_transfer_event.apply_async(
            (transactionHash, address, topics), retry=True, queue="process_txn"
        )
    return len(transfer_events)


@shared_task(bind=True, autoretry_for=(Exception,))
def pull_erc721_token(self, address, token_id):
    smart_contract = Contract.objects.get(address=address)

    try:
        Erc721Token.objects.get(smart_contract=smart_contract, token_id=token_id)
        return True
    except Erc721Token.DoesNotExist:
        if smart_contract.token_exists(token_id):
            token = Erc721Token.objects.create(
                smart_contract=smart_contract,
                collection=smart_contract.collection,
                token_id=token_id,
            )
            token.refresh_token()

            if not token.owner:
                refresh_token.apply_async(
                    (token.id, 5), queue="refresh_token", countdown=10
                )

            print(f"Pulled token: {token}")
            return True
        else:
            return False
