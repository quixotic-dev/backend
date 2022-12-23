from celery import shared_task
from celery import group
from ..common.tasks import example_add
from ..collection.tasks import refresh_collection
from ..token.tasks import pull_new_media_for_token

from api.models import Erc721Collection, Erc721Token


@shared_task
def schedule_adds():
    tasks = (example_add.s(i, i) for i in range(100))
    job = group(tasks)
    job.apply_async()
    return True


@shared_task
def refresh_collections():
    tasks = [refresh_collection.s(col.id) for col in Erc721Collection.objects.filter(approved=True)]
    job = group(tasks)
    job.apply_async()
    return f"Queued f{len(tasks)} tasks"


@shared_task
def pull_new_media():
    tokens = Erc721Token.objects.filter(
        collection__approved=True,
        approved=True
    ).exclude(image__startswith="https://fanbase-1.s3.amazonaws.com")

    i = 0
    for tok in tokens:
        pull_new_media_for_token.delay(tok.id)
        i += 1

    return f"Queued f{i} tasks"
