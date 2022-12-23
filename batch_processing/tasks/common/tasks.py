from celery import shared_task
from api.models import Erc721Token
from ...models import BatchJob


@shared_task
def job_finished(batch_job_id):
    """
    Use internal id not token id
    """
    batch_job = BatchJob.objects.get(id=batch_job_id)
    batch_job.is_finished = True
    batch_job.save()
    return True


@shared_task
def num_stale(prev_res, batch_job_id=None):
    """
    Use internal id not token id
    """
    num_stale = sum(prev_res)
    batch_job = BatchJob.objects.get(id=batch_job_id)
    batch_job.is_finished = True
    batch_job.num_stale = num_stale
    batch_job.save()
    return num_stale


@shared_task
def example_add(a, b):
    return a + b
