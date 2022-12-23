import json
import os
from urllib import request

import requests
from api.models import Contract
from django.core.files import File
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Refresh collections and contracts"

    def handle(self, *args, **kwargs):
        contracts = Contract.objects.filter(
            approved=True, network__network_id="eth-mainnet"
        )
        for c in contracts:
            if not c.collection.description:
                try:
                    url = f"https://api.simplehash.com/api/v0/nfts/ethereum/{c.address}"
                    headers = {"X-API-KEY": ""}
                    r = requests.get(url, headers=headers)
                    res = json.loads(r.text)
                    collection_metadata = res["nfts"][0]["collection"]
                    collection = c.collection

                    if "name" in collection_metadata:
                        collection.name = collection_metadata["name"]

                    if (
                        not collection.description
                        and "description" in collection_metadata
                    ):
                        collection.description = collection_metadata["description"]

                    if (
                        not collection.profile_image
                        and "image_url" in collection_metadata
                    ):
                        result = request.urlretrieve(collection_metadata["image_url"])
                        collection.profile_image.save(
                            os.path.basename(collection_metadata["image_url"]),
                            File(open(result[0], "rb")),
                        )

                    if (
                        not collection.cover_image
                        and "banner_image_url" in collection_metadata
                    ):
                        result = request.urlretrieve(
                            collection_metadata["banner_image_url"]
                        )
                        collection.cover_image.save(
                            os.path.basename(collection_metadata["banner_image_url"]),
                            File(open(result[0], "rb")),
                        )

                    if (
                        not collection.twitter_link
                        and "twitter_username" in collection_metadata
                    ):
                        collection.twitter_link = f"https://twitter.com/{collection_metadata['twitter_username']}"

                    if (
                        not collection.discord_link
                        and "discord_url" in collection_metadata
                    ):
                        collection.discord_link = collection_metadata["discord_url"]

                    if (
                        not collection.site_link
                        and "external_url" in collection_metadata
                    ):
                        collection.site_link = collection_metadata["external_url"]

                    if (
                        not collection.verified
                        and "marketplace_pages" in collection_metadata
                    ):
                        marketplace_pages = collection_metadata["marketplace_pages"]
                        for marketplace in marketplace_pages:
                            if marketplace["marketplace_id"] == "opensea":
                                collection.verified = marketplace["verified"]
                                break

                    collection.save()

                    if not collection.slug:
                        try:
                            marketplace_pages = collection_metadata["marketplace_pages"]
                            for marketplace in marketplace_pages:
                                if marketplace["marketplace_id"] == "opensea":
                                    collection.slug = marketplace[
                                        "marketplace_collection_id"
                                    ]
                                    collection.save()
                                    break
                        except Exception as e:
                            print(e)
                            pass

                except Exception as e:
                    print(e)
