from django.core.management.base import BaseCommand
from django.db import transaction
import os

from api.models import Erc721Collection
from batch_processing.tasks.collection.tasks import refresh_collection_stats
from django.core.cache import cache

CACHE_KEY = "SKIP_REFRESH_STATS"

class Command(BaseCommand):
    help = "Refresh stats for all collections"

    def handle(self, *args, **kwargs):
        if cache.get(CACHE_KEY):
            print("Cache says to skip refreshing stats.")
            return

        for col in Erc721Collection.objects.filter(approved=True):
            # self.stdout.write(f"Refreshing stats for: {col}")
            if os.environ.get("USE_CELERY"):
                refresh_collection_stats.apply_async((col.id,), queue="stats")
                cache.set(CACHE_KEY, True, 60 * 15)  # Skip refresh stats for the next 15 minutes since it just ran.
            else:
                col.refresh_stats()
