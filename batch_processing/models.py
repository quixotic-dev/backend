from django.db import models


class BatchJob(models.Model):
    name = models.CharField(max_length=36)
    num_tasks = models.PositiveIntegerField()
    description = models.TextField(null=True)

    num_stale = models.IntegerField(null=True)
    is_finished = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} #{self.id}"

    def cache_key_num_stale(self):
        return f"batch-job-{self.id}-num-stale"


class StaleOwnerRecord(models.Model):
    batch_job = models.ForeignKey(BatchJob, on_delete=models.CASCADE)
    celery_task_id = models.TextField()
    old_owner = models.TextField()
    new_owner = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)
