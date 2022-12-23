from api.models import Erc721Collection
from ..models import BatchJob
from ..tasks.common.tasks import num_stale
from ..tasks.token.tasks import refresh_token_owner
from celery import chord


def refresh_all_owners_for_collection(address):
    collection = Erc721Collection.objects.get(address=address)
    tasks = [refresh_token_owner.s(t.id) for t in collection.erc721token_set.all()]
    batch_job = BatchJob.objects.create(
        name=f"refresh-owners",
        num_tasks=len(tasks)
    )
    finished_callback = num_stale.subtask(kwargs={"batch_job_id": batch_job.id})
    job = chord(tasks, finished_callback)
    job.apply_async()
