from celery import shared_task
from django.db import transaction
from api.models import Erc721Collection
from django.core.cache import cache

@shared_task(rate_limit="4/s")
def refresh_collection(internal_id):
    with transaction.atomic():
        col = Erc721Collection.objects.select_for_update().get(id=internal_id)
        col.refresh_collection()
        return col.address


@shared_task
def pull_token_id_for_collection(col_internal_id, token_id):
    """
    Use internal id not token id
    """
    col = Erc721Collection.objects.get(id=col_internal_id)
    col.pull_erc721_token(token_id)
    return True


@shared_task(rate_limit="15/s", ignore_result=True)
def refresh_collection_stats(col_internal_id):
    cache_key = f"SHOULD_SKIP_REFRESH_{col_internal_id}"
    if cache.get(cache_key):
        return "Skipped"

    collection = Erc721Collection.objects.get(id=col_internal_id)
    before_sales_num = collection.sales
    collection.refresh_stats()
    after_sales_num = collection.sales
    if before_sales_num == after_sales_num:
        cache.set(cache_key, 1, 10 * 60)  # Skip for the next 15 minutes bc last refresh didnt do anything.
    return "Success"
