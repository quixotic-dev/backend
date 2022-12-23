#!/usr/bin/env python -W ignore

import os
import subprocess
from pymemcache.client.base import Client

RELEASE_PHASE_IN_PROGRESS = "RELEASE_PHASE_IN_PROGRESS"


def run():
    cache_client = Client(os.environ.get("MEMCACHEDCLOUD_SERVERS"))
    if cache_client.get(RELEASE_PHASE_IN_PROGRESS):
        print("Release phase already in progress on another worker")
        return

    cache_client = cache_client.set(RELEASE_PHASE_IN_PROGRESS, True, 60)
    if os.environ.get("AUTO_MIGRATE") and int(os.environ.get("AUTO_MIGRATE")):
        print("Running migrations")
        p = subprocess.run(
            ["python", "manage.py", "migrate"], capture_output=True, text=True
        )
        print(p.stdout)
        print(p.stderr)
    else:
        print("Skipping migrations")


run()
print("Release sequence finished.")
