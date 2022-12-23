import json
import os
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from random import shuffle
from time import sleep

import requests
from django.core.cache import cache
from django.db import models
from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import Coalesce, TruncDate
from django.utils.translation import gettext_lazy as _
from web3 import Web3

from api.rewards.utils import (
    get_amount_distributed,
    get_boost_per_mille,
    get_budget,
    is_campaign_active,
    is_eligible_for_boost,
)
from api.utils.constants import (
    ALCHEMY_API_KEY,
    ALCHEMY_URL,
    ETH_ALCHEMY_URL,
    EXCHANGE_CONTRACT_V6_ADDRESS,
    NETWORK,
    L2ERC721_BRIDGE
)
from api.utils.email_utils import (
    send_email_about_campaign_budget,
    send_email_about_campaign_distribution,
)
from api.utils.ens_utils import get_address_for_ens, get_ens_for_address
from api.utils.Erc20Contract import Erc20Contract
from api.utils.Erc721Contract import Erc721Contract
from api.utils.Erc1155Contract import Erc1155Contract
from api.utils.ExchangeContract import order_is_active, sell_order_is_active
from api.utils.process_transfer import handle_transfer_event
from api.utils.restricted_usernames import is_restricted

from .cache_utils.cache_utils import cache_func
from .utils.address_utils import is_address_eoa

from rest_framework_api_key.models import APIKey

ETH_ID = 1
WETH_ID = 2
OP_ID = 3


class Profile(models.Model):
    address = models.TextField(db_index=True, unique=True)
    username = models.TextField(db_index=True, unique=True, null=True, blank=True)

    profile_image = models.ImageField(
        upload_to="quixotic-user-profile/", max_length=512, null=True, blank=True
    )
    cover_image = models.ImageField(
        upload_to="quixotic-user-cover/", max_length=512, null=True, blank=True
    )
    bio = models.TextField(blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    twitter = models.URLField(blank=True, null=True)
    minimum_offer = models.PositiveBigIntegerField(blank=True, null=True)

    reverse_ens = models.TextField(null=True, blank=True, unique=True)

    # Internal flags
    notifications_read = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.address}"

    # NOTE: This is dependent on the Collection <> Token model relationship
    def collections(self):
        collections = (
            Erc721Collection.objects.filter(
                Q(erc721token__owner=self)
                | Q(erc721token__erc1155tokenowner__owner=self),
                approved=True,
            )
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        return collections

    # NOTE: This is dependent on the Collection <> Token model relationship
    def erc721Collections(self):
        collections = (
            Erc721Collection.objects.filter(
                erc721token__owner=self,
                approved=True,
            )
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        return collections

    def erc721tokens(self):
        if os.environ.get("DATABASE_FOLLOWER_CONNECTION_POOL_URL"):
            tokens = Erc721Token.objects.using("follower")
        else:
            tokens = Erc721Token.objects

        tokens = (
            tokens.filter(
                Q(owner=self) | Q(pending_owner=self),
                approved=True,
                collection__approved=True,
            )
            .exclude(hiddentoken__user=self)
            .order_by("-for_sale", "-price_eth", "-collection", "-id")
        )

        return tokens

    # NOTE: This is dependent on the Collection <> Token model relationship
    def tokens(self, pull_erc721s=True, pull_erc1155s=True):
        if os.environ.get("DATABASE_FOLLOWER_CONNECTION_POOL_URL"):
            tokens = Erc721Token.objects.using("follower")
        else:
            tokens = Erc721Token.objects

        q_filters = Q()
        if pull_erc721s:
            q_filters = q_filters | Q(owner=self) | Q(pending_owner=self)
        if pull_erc1155s:
            q_filters = q_filters | Q(erc1155tokenowner__owner=self)

        tokens = (
            tokens.filter(
                q_filters,
                approved=True,
                collection__approved=True,
            )
            .exclude(hiddentoken__user=self)
            .order_by("-for_sale", "-price_eth", "-collection", "-id")
        )
        return tokens

    # NOTE: This is dependent on the Collection <> Token model relationship
    def all_tokens(self):
        tokens = Erc721Token.objects.filter(
            Q(owner=self) | Q(erc1155tokenowner__owner=self),
            approved=True,
            collection__approved=True,
        )
        return tokens

    # NOTE: This is dependent on the Collection <> Token model relationship
    def hidden_tokens(self):
        tokens = Erc721Token.objects.filter(
            Q(owner=self) | Q(erc1155tokenowner__owner=self),
            approved=True,
            collection__approved=True,
            hiddentoken__user=self,
        )
        return tokens

    # NOTE: This is dependent on the Collection <> Token model relationship
    def activity(self):
        on_chain_activity = Erc721Activity.objects.filter(
            (Q(from_profile=self) | Q(to_profile=self)),
            token__approved=True,
            token__collection__approved=True,
        )
        off_chain_activity = OffChainActivity.objects.filter(
            (Q(from_profile=self) | Q(to_profile=self)),
            token__approved=True,
            token__collection__approved=True,
        )
        activity = on_chain_activity.union(off_chain_activity).order_by("-timestamp")
        return activity

    def likes(self):
        return self.tokenlike_set.filter(token__collection__approved=True)

    def follower_count(self):
        return self.followers.count()

    def followed_collections(self):
        return (
            self.profilefollow_set.filter(followed_collection__approved=True)
            .exclude(followed_collection=None)
            .values_list("followed_collection__address", flat=True)
        )

    def followed_profiles(self):
        return self.profilefollow_set.exclude(followed_profile=None).values_list(
            "followed_profile__address", flat=True
        )

    def followed_collections_full(self):
        collection_ids = (
            self.profilefollow_set.filter(followed_collection__approved=True)
            .exclude(followed_collection=None)
            .values_list("followed_collection_id", flat=True)
        )
        return Erc721Collection.objects.filter(id__in=collection_ids).order_by(
            "-volume_7d"
        )[:12]

    def followed_profiles_full(self):
        profile_ids = list(
            self.profilefollow_set.exclude(followed_profile=None).values_list(
                "followed_profile_id", flat=True
            )
        )
        shuffle(profile_ids)
        return Profile.objects.filter(id__in=profile_ids[:12])

    def refresh_ens(self, should_save=True):
        ens = get_ens_for_address(self.address)
        address = get_address_for_ens(ens)

        if address == self.address and not is_restricted(ens):
            try:
                existing_profile = Profile.objects.get(reverse_ens=ens)
                if self != existing_profile:
                    existing_profile.reverse_ens = None
                    existing_profile.save()
                    self.reverse_ens = ens
            except Exception:
                self.reverse_ens = ens
        else:
            self.reverse_ens = None

        if should_save:
            self.save()

    def save(self, *args, **kwargs):
        assert Web3.isChecksumAddress(
            self.address
        ), f"Profile address must be a checksum address: {self.address}"
        if self.username == "":
            self.username = None
        self.refresh_ens(should_save=False)
        return super(Profile, self).save(*args, **kwargs)

    def pull_tokens_for_profile_for_collection(self, collection_address):
        from batch_processing.tasks.token.tasks import (
            pull_erc721_token as queue_pull_erc_721_token,
        )

        contract = Erc721Contract(collection_address, NETWORK)
        num_tokens = contract.balance_of(self.address)
        for i in range(num_tokens):
            token_id = contract.token_of_owner_by_index(self.address, i)
            if os.environ.get("USE_CELERY"):
                task_id = queue_pull_erc_721_token.apply_async(
                    (collection_address, token_id),
                    queue="pull_token",
                    ignore_result=True,
                )
                print(task_id)
            else:
                raise Exception("Must turn on queue to pull token")


class CollectionCategory(models.TextChoices):
    ART = "AR", _("Art")
    COLLECTIBLES = "CO", _("Collectibles")
    MUSIC = "MU", _("Music")
    PHOTOGRAPHY = "PH", _("Photography")
    SPORTS = "SP", _("Sports")
    UTILITY = "UT", _("Utility")
    VIRTUAL_WORLDS = "VW", _("Virtual Worlds")


class CollectionSort(models.TextChoices):
    PRICE_ASC = "PA", _("price:asc")
    PRICE_DESC = "PD", _("price:desc")
    EXPIRATION_ASC = "EA", _("expiration_timestamp:asc")
    EXPIRATION_DESC = "ED", _("expiration_timestamp:desc")
    LISTED_ASC = "LA", _("listed_timestamp:asc")
    LISTED_DESC = "LD", _("listed_timestamp:desc")
    HIGHEST_OFFER = "HO", _("highest_offer:desc")


class PaymentToken(models.Model):
    address = models.TextField(unique=True)
    name = models.TextField()
    symbol = models.TextField()

    def __str__(self):
        return self.symbol


class CollectionType(models.TextChoices):
    ERC1155 = "1155", _("ERC-1155")
    ERC721 = "721", _("ERC-721")


class CollectionAnimationType(models.TextChoices):
    IMAGE = "I", _("Image")
    VIDEO = "V", _("Video")
    AUDIO = "A", _("Audio")
    HTML = "H", _("HTML")
    MODEL = "M", _("3D Model")


class Network(models.Model):
    name = models.TextField()
    network_id = models.TextField(unique=True)
    network = models.TextField()
    chain_id = models.TextField()

    def __str__(self):
        return f"{self.network_id}"


class Contract(models.Model):
    class Meta:
        unique_together = ("address", "network")

    collection = models.ForeignKey(
        "Erc721Collection", blank=True, null=True, on_delete=models.SET_NULL
    )

    # Contract details
    address = models.TextField()
    network = models.ForeignKey(Network, on_delete=models.PROTECT, default=1)
    name = models.TextField(blank=True, null=True)
    symbol = models.TextField(blank=True, null=True, editable=False)
    owner = models.ForeignKey(Profile, on_delete=models.PROTECT, blank=True, null=True)
    total_supply = models.PositiveIntegerField(blank=True, null=True)
    type = models.CharField(
        max_length=4, choices=CollectionType.choices, default=CollectionType.ERC721
    )
    created = models.DateTimeField(null=True, blank=True)

    # Internal fields
    approved = models.BooleanField(default=False)
    last_supply_check = models.DateTimeField(blank=True, null=True)
    is_bridged = models.BooleanField(default=False)

    def __str__(self):
        if self.address and len(self.address) > 4:
            return f"{self.name} ({self.address[:5]})"
        else:
            return f"{self.name}"

    def token_exists(self, token_id):
        if self.type == CollectionType.ERC721:
            contract = Erc721Contract(
                self.address,
                self.network.network_id,
            )
            owner = contract.owner_of(token_id)
            if owner:
                return True
            else:
                return False
        elif self.type == CollectionType.ERC1155:
            contract = Erc1155Contract(self.address, self.network.network_id)
            try:
                return contract.token_uri(token_id) != ""
            except Exception:
                return False

    def is_layer1(self):
        return self.network.chain_id in ("0x1", "0x5")

    def pull_new_tokens(self):
        token_count = Erc721Token.objects.filter(smart_contract=self).count()

        if self.total_supply and token_count < self.total_supply:
            import concurrent.futures

            print(f"Pulling new tokens for {self.name} ({self.address})")
            if self.type == CollectionType.ERC721:
                contract = Erc721Contract(self.address, self.network.network_id)
                events = contract.transfer_events_from_address(
                    address="0x0000000000000000000000000000000000000000"
                )
                with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
                    token_ids = set(
                        Erc721Token.objects.filter(smart_contract=self).values_list(
                            "token_id", flat=True
                        )
                    )
                    events = [
                        e for e in events if str(e["args"]["tokenId"]) not in token_ids
                    ]
                    for event in events:
                        token_id = event["args"]["tokenId"]
                        if not Erc721Token.objects.filter(
                                smart_contract=self, token_id=token_id
                        ).exists():
                            sleep(0.01)
                            future = pool.submit(self.pull_erc721_token, token_id)
                        else:
                            print(f"Skipping: {token_id}")

            elif self.type == CollectionType.ERC1155:
                contract = Erc1155Contract(self.address, self.network.network_id)
                single_events = contract.single_transfer_events_from_address(
                    address="0x0000000000000000000000000000000000000000"
                )
                batch_events = contract.batch_transfer_events_from_address(
                    address="0x0000000000000000000000000000000000000000"
                )
                events = single_events + batch_events
                with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
                    token_ids = set(
                        Erc721Token.objects.filter(smart_contract=self).values_list(
                            "token_id", flat=True
                        )
                    )
                    events = [
                        e for e in events if str(e["args"]["id"]) not in token_ids
                    ]
                    for event in events:
                        token_id = event["args"]["id"]
                        if not Erc721Token.objects.filter(
                                smart_contract=self, token_id=token_id
                        ).exists():
                            sleep(0.01)
                            future = pool.submit(self.pull_erc1155_token, token_id)
                        else:
                            print(f"Skipping: {token_id}")

    def pull_erc721_token(self, token_id, queue=True):
        print(f"Starting to pull token index: {token_id}")

        if os.environ.get("USE_CELERY") and queue:
            from batch_processing.tasks.token.tasks import (
                pull_erc721_token as queue_pull_erc_721_token,
            )

            queue_pull_erc_721_token.apply_async(
                (self.address, token_id), queue="pull_token", ignore_result=True
            )
            return

        try:
            return Erc721Token.objects.get(smart_contract=self, token_id=token_id)
        except Erc721Token.DoesNotExist:
            token = Erc721Token.objects.create(
                smart_contract=self,
                collection=self.collection,
                token_id=token_id,
            )
            token.refresh_token()

            retries = 5
            while not token.owner and retries > 0:
                token.refresh_token()
                if retries < 5:
                    sleep(10 - retries)
                retries -= 1
                print(f"Retrying... {token}")

                if retries == 0:
                    raise Exception("Failed to pull 5 times")

            print(f"Pulled token: {token}")
            return token

    def pull_erc1155_token(self, token_id, queue=True):
        print(f"Starting to pull token index: {token_id}")

        try:
            return Erc721Token.objects.get(smart_contract=self, token_id=token_id)
        except Erc721Token.DoesNotExist:
            token = Erc721Token.objects.create(
                smart_contract=self,
                collection=self.collection,
                token_id=token_id,
            )
            token.refresh_token()
            token.refresh_erc1155_owners()

            print(f"Pulled token: {token}")
            return token

    def set_created_date(self):
        w3 = Web3(
            Web3.HTTPProvider(
                f"https://{self.network.network_id}.g.alchemy.com/v2/{ALCHEMY_API_KEY}"
            )
        )

        data = {
            "jsonrpc": "2.0",
            "method": "eth_getLogs",
            "params": [
                {
                    "fromBlock": "0x1",
                    "toBlock": "latest",
                    "address": self.address,
                    "topics": [
                        "0x8be0079c531659141344cd1fd0a4f28419497f9722a3daafe3b4186f6b6457e0",
                        "0x0000000000000000000000000000000000000000000000000000000000000000",
                    ],
                }
            ],
            "id": 1,
        }

        if self.network.network_id == NETWORK:
            r = requests.post(ALCHEMY_URL, json=data)
        else:
            r = requests.post(ETH_ALCHEMY_URL, json=data)
        r_json = json.loads(r.text)

        try:
            if (
                    "result" in r_json
                    and len(r_json["result"]) > 0
                    and "transactionHash" in r_json["result"][0]
            ):
                full_txn = w3.eth.get_transaction(
                    r_json["result"][0]["transactionHash"]
                )

                try:
                    timestamp = datetime.fromtimestamp(
                        int(full_txn["l1Timestamp"], 16), timezone.utc
                    )
                except Exception:
                    timestamp = datetime.fromtimestamp(
                        w3.eth.getBlock(full_txn["blockNumber"]).timestamp, timezone.utc
                    )

                self.created = timestamp
                self.save()
        except Exception:
            pass

    def refresh_contract(self):
        if self.type == CollectionType.ERC721:
            contract = Erc721Contract(self.address, self.network.network_id)
        elif self.type == CollectionType.ERC1155:
            contract = Erc1155Contract(self.address, self.network.network_id)

        if not self.name:
            self.name = contract.name()

        if not self.symbol:
            self.symbol = contract.symbol()

        # Refresh contract owner
        try:
            owner_address = contract.owner()
            profile, created = Profile.objects.get_or_create(address=owner_address)
            self.owner = profile
        except Exception:
            print("Could not find contract owner")

        self.save()

        # Set contract deployment date
        if self.owner and not created:
            self.set_created_date()

        # Refresh total supply
        try:
            supply = contract.total_supply(self.last_supply_check)
            if supply or supply == 0:
                self.total_supply = supply
                self.last_supply_check = datetime.now(tz=timezone.utc)
        except Exception:
            print("Could not get total supply")

        try:
            self.save()
        except Exception as e:
            print("Error saving total supply")
            print(e)


# TODO: Rename to generic 'Collection'
class Erc721Collection(models.Model):
    class Meta:
        verbose_name = "Collection"
        unique_together = ("address", "network")

    primary_contract = models.OneToOneField(
        Contract,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )

    # Collection details
    name = models.TextField(blank=True, null=True)
    symbol = models.TextField(blank=True, null=True, editable=False)
    owner = models.ForeignKey(Profile, on_delete=models.PROTECT, blank=True, null=True)
    type = models.CharField(
        max_length=4, choices=CollectionType.choices, default=CollectionType.ERC721
    )

    # Collection royalties
    royalty_per_mille = models.PositiveSmallIntegerField(blank=True, null=True)
    payout_address = models.TextField(blank=True, null=True)

    # Collection settings
    profile_image = models.ImageField(
        upload_to="quixotic-collection-profile/",
        max_length=10000,
        null=True,
        blank=True,
    )
    profile_image_url = models.URLField(null=True, blank=True, max_length=750)
    profile_image_hash = models.CharField(null=True, blank=True, max_length=750)
    cover_image = models.ImageField(
        upload_to="quixotic-collection-cover/", max_length=512, null=True, blank=True
    )
    seo_image = models.ImageField(
        upload_to="quixotic-collection-seo-image/",
        max_length=10000,
        null=True,
        blank=True,
    )
    slug = models.SlugField(db_index=True, unique=True, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    twitter_link = models.URLField(blank=True, null=True)
    discord_link = models.URLField(blank=True, null=True)
    site_link = models.URLField(blank=True, null=True)
    display_theme = models.PositiveSmallIntegerField(default=1)
    category = models.CharField(
        max_length=2, choices=CollectionCategory.choices, null=True, blank=True
    )
    ranking_enabled = models.BooleanField(default=False)

    # Collection flags
    approved = models.BooleanField(default=False)
    verified = models.BooleanField(default=False)
    is_spam = models.BooleanField(default=False)
    non_transferable = models.BooleanField(default=False)
    delisted = models.BooleanField(default=False)

    # Internal fields
    default_sort = models.CharField(
        max_length=2, choices=CollectionSort.choices, null=True, blank=True
    )
    animation_url_type = models.CharField(
        max_length=1, choices=CollectionAnimationType.choices, null=True, blank=True
    )

    # Collection stats
    floor = models.PositiveBigIntegerField(blank=True, null=True)
    volume = models.PositiveBigIntegerField(blank=True, null=True, default=0)
    volume_24h = models.PositiveBigIntegerField(blank=True, null=True, default=0)
    volume_7d = models.PositiveBigIntegerField(blank=True, null=True, default=0)
    volume_30d = models.PositiveBigIntegerField(blank=True, null=True, default=0)
    volume_prev_24h = models.PositiveBigIntegerField(blank=True, null=True, default=0)
    volume_prev_7d = models.PositiveBigIntegerField(blank=True, null=True, default=0)
    volume_prev_30d = models.PositiveBigIntegerField(blank=True, null=True, default=0)
    sales = models.PositiveIntegerField(blank=True, null=True, default=0)
    sales_24h = models.PositiveIntegerField(blank=True, null=True, default=0)
    sales_7d = models.PositiveIntegerField(blank=True, null=True, default=0)
    sales_30d = models.PositiveIntegerField(blank=True, null=True, default=0)
    supply = models.PositiveBigIntegerField(blank=True, null=True, default=0)
    listed = models.PositiveIntegerField(blank=True, null=True, default=0)
    owners = models.PositiveIntegerField(blank=True, null=True, default=0)

    # TODO: Delete
    address = models.TextField()
    network = models.ForeignKey(Network, on_delete=models.PROTECT, default=1)
    l1_address = models.TextField(blank=True, null=True)
    total_supply = models.PositiveIntegerField(blank=True, null=True)
    last_supply_pull = models.DateTimeField(blank=True, null=True, editable=False)

    # Boost related
    is_eligible_for_boost = models.BooleanField(default=False)
    is_boost_active = models.BooleanField(default=False)

    # Performance Flags
    disable_attribute_lookup = models.BooleanField(default=False)

    # NOTE: This is dependent on the Collection <> Token model relationship
    def refresh_stats(self):
        from .utils.collection_stats import (
            collection_24h_sales,
            collection_24h_volume,
            collection_floor_price,
            collection_listed_count,
            collection_prev_24h_volume,
            collection_prev_Xd_volume,
            collection_sales,
            collection_supply,
            collection_unique_owners,
            collection_volume,
            collection_Xd_sales,
            collection_Xd_volume,
        )

        using = "default"
        if os.environ.get("DATABASE_FOLLOWER_CONNECTION_POOL_URL"):
            using = "follower"

        self.floor = collection_floor_price(self, using)
        self.volume = collection_volume(self, using)
        self.volume_24h = collection_24h_volume(self, using)
        self.volume_7d = collection_Xd_volume(self, 7, using)
        self.volume_30d = collection_Xd_volume(self, 30, using)

        self.volume_prev_24h = collection_prev_24h_volume(self, using)
        self.volume_prev_7d = collection_prev_Xd_volume(self, 7, using)
        self.volume_prev_30d = collection_prev_Xd_volume(self, 30, using)

        self.sales = collection_sales(self, using)
        self.sales_24h = collection_24h_sales(self, using)
        self.sales_7d = collection_Xd_sales(self, 7, using)
        self.sales_30d = collection_Xd_sales(self, 30, using)

        self.supply = collection_supply(self, using)
        self.listed = collection_listed_count(self, using)
        self.owners = collection_unique_owners(self, using)
        self.save()

    def __str__(self):
        if self.address and len(self.address) > 4:
            return f"{self.name} ({self.address[:5]})"
        else:
            return f"{self.name}"

    def blockchain(self):
        return self.network.network_id

    def payment_tokens(self):
        tokens = PaymentToken.objects.all()
        return tokens

    def floor_price(self):
        try:
            eth_to_op = BlockchainState.objects.get(key="eth_op_price").value
            eth_to_usd = BlockchainState.objects.get(key="eth_usd_price").value
            floor_price = {
                "ETH": self.floor,
                "WETH": self.floor,
                "USD": self.floor * float(eth_to_usd),
                "OP": self.floor * float(eth_to_op),
            }
            return floor_price
        except Exception:
            floor_price = {"ETH": self.floor, "WETH": self.floor}
            return floor_price

    # NOTE: This is dependent on the Collection <> Token model relationship
    def image_url(self):
        if self.profile_image:
            return self.profile_image.url
        elif self.profile_image_url:
            return self.profile_image_url
        else:
            first_token = (
                Erc721Token.objects.filter(collection=self)
                .exclude(image=None)
                .order_by("token_id")
                .first()
            )
            if first_token:
                self.profile_image = first_token.image
                # self.save()
                return first_token.image
            else:
                return None

    def category_name(self):
        return self.get_category_display()

    def categories(self):
        return CollectionCategory.choices

    def default_sort_str(self):
        return self.get_default_sort_display()

    def contract_type(self):
        return self.get_type_display()

    def eth_to_usd(self):
        try:
            return float(BlockchainState.objects.get(key="eth_usd_price").value)
        except Exception:
            return None

    def volume_change_24h(self):
        if self.volume_prev_24h > 0:
            return (self.volume_24h - self.volume_prev_24h) / self.volume_prev_24h
        else:
            return None

    def volume_change_7d(self):
        if self.volume_prev_7d > 0:
            return (self.volume_7d - self.volume_prev_7d) / self.volume_prev_7d
        else:
            return None

    def volume_change_30d(self):
        if self.volume_prev_30d > 0:
            return (self.volume_30d - self.volume_prev_30d) / self.volume_prev_30d
        else:
            return None

    # NOTE: This is dependent on the Collection <> Token model relationship
    def daily_stats(self):
        from .utils.collection_stats import collection_daily_stats

        return collection_daily_stats(self)

    # NOTE: This is dependent on the Collection <> Token model relationship
    def activity(self):
        on_chain_activity = Erc721Activity.objects.filter(token__collection=self)
        off_chain_activity = OffChainActivity.objects.filter(token__collection=self)
        activity = on_chain_activity.union(off_chain_activity).order_by("-timestamp")
        return activity

    # NOTE: This is dependent on the Collection <> Token model relationship
    def attributes(self):
        attributes_key = f"attributes__{self.address}"
        if res := cache.get(attributes_key):
            return res

        attribute_tuples = (
            Erc721TokenAttribute.objects.filter(token__collection=self)
            .exclude(token__owner__address="0x0000000000000000000000000000000000000000")
            .values_list("trait_type", "value")
            .annotate(count=Count("token"))
            .order_by()
        )

        attribute_list = []
        attribute_dict = defaultdict(list)

        if not self.supply or self.supply < 1:
            return []

        for trait_type, value, attr_count in attribute_tuples:
            rarity = min(int(attr_count) / self.supply, 1)
            attribute_dict[trait_type].append((value, rarity))

        for key in attribute_dict.keys():
            attribute_list.append(
                {"trait_type": key, "value": tuple(attribute_dict[key])}
            )

        if len(attribute_list) > 25000:
            return []

        cache.set(attributes_key, attribute_list, 60 * 5)  # 5 minutes
        return attribute_list

    # NOTE: This is dependent on the Collection <> Token model relationship
    def attribute_lookup(self):
        if self.disable_attribute_lookup:
            return {}

        if not self.supply or self.supply < 1:
            return {}

        attributes_lookup_key = f"attribute_lookup__{self.address}"
        if res := cache.get(attributes_lookup_key):
            return res

        attribute_tuples = (
            Erc721TokenAttribute.objects.filter(token__collection=self)
            .exclude(token__owner__address="0x0000000000000000000000000000000000000000")
            .values_list("trait_type", "value")
            .annotate(count=Count("token"))
            .order_by()
        )

        attribute_lookup = {}
        for trait_type, value, attr_count in attribute_tuples:
            attribute_lookup[f"{trait_type}:{value}"] = attr_count

        if len(attribute_lookup) > 25000:
            cache.set(attributes_lookup_key, {}, 60 * 60 * 24)  # Cache for 24 hours
            return {}

        cache.set(attributes_lookup_key, attribute_lookup, 60 * 15)  # 15 minutes
        return attribute_lookup

    # NOTE: This is dependent on the Collection <> Token model relationship
    def rarity_lookup(self):
        rarity_lookup_key = f"rarity_lookup__{self.address}"
        if res := cache.get(rarity_lookup_key):
            return res

        rarity_scores = {}
        rarity_ranks = {}
        attribute_lookup = self.attribute_lookup()
        if not self.supply or self.supply < 1:
            return {}

        # Calculate rarity score for each token
        tokens = self.erc721token_set.exclude(
            owner__address="0x0000000000000000000000000000000000000000"
        )

        for token in tokens:
            rarity_score = 0
            for attr in token.erc721tokenattribute_set.all():
                attr_count = attribute_lookup.get(
                    f"{attr.trait_type}:{attr.value}", None
                )
                if attr_count:
                    rarity_score += 1 / (attr_count / self.supply)
            rarity_scores[token.token_id] = rarity_score

        # Create ordered list of all rarity scores
        sorted_scores = list(rarity_scores.values())
        sorted_scores.sort(reverse=True)

        # Get the rank for each token using the ordered index of its rarity score
        for token_id, rarity_score in rarity_scores.items():
            rarity_ranks[token_id] = sorted_scores.index(rarity_score) + 1

        cache.set(rarity_lookup_key, rarity_ranks, 60 * 5)
        return rarity_ranks

    # NOTE: This is dependent on the Collection <> Token model relationship
    def refresh_ranks(self):
        for token in self.erc721token_set.all():
            token.refresh_rank()

    # NOTE: This is dependent on the Collection <> Token model relationship
    def refresh_animation_url_type(self, should_save=True):
        from .utils.metadata_utils import refresh_collection_animation_url_type

        return refresh_collection_animation_url_type(self, should_save=should_save)

    # NOTE: This is dependent on the Collection address field
    def refresh_metadata(self, should_save=True):
        from .utils.metadata_utils import refresh_collection_metadata

        return refresh_collection_metadata(self, should_save=should_save)

    # EIP-2981 Royalties
    def refresh_royalty_info(self, should_save=True):
        if not self.payout_address and not self.royalty_per_mille:
            print("Refreshing royalty info")

            # This check works for 721s and 1155s because the royalty_info function has the same signature.
            contract = Erc721Contract(
                self.primary_contract.address, self.primary_contract.network.network_id
            )
            royalty_info = contract.royalty_info()

            if royalty_info:
                self.payout_address = Web3.toChecksumAddress(royalty_info[0])
                self.royalty_per_mille = min(royalty_info[1] * 10, 150)
            else:
                self.payout_address = "0x0000000000000000000000000000000000000000"
                self.royalty_per_mille = 0

            if should_save:
                self.save()

    def refresh_collection(self):
        if self.primary_contract.type == CollectionType.ERC721:
            contract = Erc721Contract(
                self.primary_contract.address, self.primary_contract.network.network_id
            )
        elif self.primary_contract.type == CollectionType.ERC1155:
            contract = Erc1155Contract(
                self.primary_contract.address, self.primary_contract.network.network_id
            )

        if not self.name:
            self.name = contract.name()

        if not self.symbol:
            self.symbol = contract.symbol()

        if not self.animation_url_type:
            self.refresh_animation_url_type(should_save=False)

        self.owner = self.primary_contract.owner

        # self.refresh_metadata(should_save=False)
        self.refresh_royalty_info(should_save=False)

        self.save()

    def save(self, *args, **kwargs):
        assert Web3.isChecksumAddress(
            self.address
        ), "Collection address must be a checksum address"
        ETH_NETWORK_ID = 2
        if (
                self.payout_address
                and "opt" in NETWORK
                and self.primary_contract.network.id == ETH_NETWORK_ID
                and not is_address_eoa(self.payout_address, l1=True)
        ):
            print("ETH L1 Payout Address is not an EOA. Setting Royalty to 0.")
            self.payout_address = "0x0000000000000000000000000000000000000000"
            self.royalty_per_mille = 0
        return super(Erc721Collection, self).save(*args, **kwargs)


# TODO: Rename to generic 'Token'
class Erc721Token(models.Model):
    class Meta:
        verbose_name = "Token"
        unique_together = ("smart_contract", "token_id")
        indexes = [
            models.Index(fields=["id", "approved", "collection", "owner"]),
            models.Index(fields=["approved"]),
        ]

    # Token details
    collection = models.ForeignKey(Erc721Collection, on_delete=models.PROTECT)
    smart_contract = models.ForeignKey(
        Contract, on_delete=models.PROTECT, null=True, blank=True
    )
    token_id = models.CharField(max_length=128)
    owner = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True)
    quantity = models.PositiveIntegerField(default=1)
    name = models.TextField()
    description = models.TextField(null=True, blank=True)
    external_url = models.URLField(null=True, blank=True)
    background_color = models.CharField(null=True, blank=True, max_length=7)
    image = models.URLField(null=True, blank=True, max_length=10000)
    image_src = models.CharField(null=True, blank=True, max_length=10000)
    animation_url = models.URLField(null=True, blank=True, max_length=10000)
    animation_url_src = models.CharField(null=True, blank=True, max_length=750)
    rank = models.PositiveIntegerField(null=True, blank=True)

    # Listing details
    for_sale = models.BooleanField(default=False)
    price = models.BigIntegerField(blank=True, null=True)
    price_eth = models.BigIntegerField(blank=True, null=True)
    listed_timestamp = models.DateTimeField(null=True, blank=True)
    expiration_timestamp = models.DateTimeField(null=True, blank=True)
    payment_token = models.ForeignKey(
        PaymentToken,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="price",
    )

    # Last sale details
    last_sale_price = models.BigIntegerField(blank=True, null=True)
    last_sale_price_eth = models.BigIntegerField(blank=True, null=True)
    last_sale_payment_token = models.ForeignKey(
        PaymentToken,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="last_sale",
    )

    # Offer details
    highest_offer = models.BigIntegerField(blank=True, null=True)
    highest_offer_eth = models.BigIntegerField(blank=True, null=True)
    highest_offer_payment_token = models.ForeignKey(
        PaymentToken,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="highest_offer",
    )

    # Internal fields
    approved = models.BooleanField(default=True)
    last_media_pull = models.DateTimeField(blank=True, null=True, editable=False)
    is_airdrop = models.BooleanField(default=False)
    pending_owner = models.ForeignKey(
        Profile, on_delete=models.PROTECT, related_name="bridge_withdrawals", null=True
    )
    pending_deposit = models.BooleanField(default=False)

    # TODO: Delete
    is_l1 = models.BooleanField(default=False)
    is_bridged = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name}"

    def contract_address(self):
        return self.smart_contract.address

    def bridged(self):
        return self.smart_contract.is_bridged

    def network(self):
        return self.smart_contract.network.network_id

    def owners(self):
        if self.smart_contract.type == CollectionType.ERC721:
            return []
        elif self.smart_contract.type == CollectionType.ERC1155:
            return Erc1155TokenOwner.objects.filter(token=self)

    def sell_order(self):
        if self.collection.delisted:
            return None

        orders = sorted(
            self.erc721sellorder_set.filter(active=True), key=lambda x: x.eth_price()
        )
        return orders[0] if orders else None

    def dutch_auction(self):
        if self.collection.delisted:
            return None

        orders = sorted(
            self.erc721dutchauction_set.filter(active=True), key=lambda x: x.eth_price()
        )
        return orders[0] if orders else None

    def buy_order(self):
        if self.collection.delisted:
            return None

        orders = sorted(
            self.erc721buyorder_set.filter(active=True),
            key=lambda x: x.eth_price(),
            reverse=True,
        )
        return orders[0] if orders else None

    def sell_orders(self):
        orders = sorted(
            self.erc721sellorder_set.filter(active=True), key=lambda x: x.eth_price()
        )
        return orders

    def dutch_auctions(self):
        orders = sorted(
            self.erc721dutchauction_set.filter(active=True), key=lambda x: x.eth_price()
        )
        return orders

    def buy_orders(self):
        orders = sorted(
            self.erc721buyorder_set.filter(active=True),
            key=lambda x: x.eth_price(),
            reverse=True,
        )
        return orders

    def minimum_offer(self):
        try:
            threshold = CollectionOfferThreshold.objects.get(
                collection=self.collection, profile=self.owner
            )
            eth_to_op = BlockchainState.objects.get(key="eth_op_price").value
            weth_offer = threshold.minimum_offer / 1000000000
            op_offer = weth_offer * float(eth_to_op)
            offer_thresholds = {"WETH": weth_offer, "OP": op_offer}
            return offer_thresholds
        except Exception:
            return None

    def activity(self):
        on_chain_activity = Erc721Activity.objects.filter(token=self)
        off_chain_activity = OffChainActivity.objects.filter(token=self)
        activity = on_chain_activity.union(off_chain_activity).order_by("-timestamp")
        return activity

    def price_history(self):
        sales_key = f"token_sales__{self.id}"
        if res := cache.get(sales_key):
            return res

        raw_daily_stats = (
            Erc721Activity.objects.annotate(
                coalesce_payment_token=Coalesce(
                    "sell_order__payment_token__symbol",
                    "buy_order__payment_token__symbol",
                    "dutch_auction__payment_token__symbol",
                )
            )
            .filter(
                token=self,
                event_type_short="SA",
            )
            .filter(Q(coalesce_payment_token="ETH") | Q(coalesce_payment_token="WETH"))
            .annotate(
                date_sold=TruncDate(
                    Coalesce(
                        "sell_order__time_sold",
                        "buy_order__time_sold",
                        "dutch_auction__time_sold",
                    )
                )
            )
            .values("date_sold")
            .annotate(
                volume=Sum(
                    Coalesce(
                        "sell_order__price", "buy_order__price", "dutch_auction__price"
                    )
                )
            )
            .annotate(
                avg_price=Avg(
                    Coalesce(
                        "sell_order__price", "buy_order__price", "dutch_auction__price"
                    )
                )
            )
            .annotate(num_traded=Count("id"))
            .order_by("date_sold")
        )

        i = 0
        daily_stats = []
        for stat in raw_daily_stats:
            stat_json = {
                "date": stat["date_sold"],
                "avg_price": int(stat["avg_price"]) / (10 ** 9),
            }
            daily_stats.append(stat_json)
            i += 1

        cache.set(sales_key, daily_stats, 60)
        return daily_stats

    # NOTE: This is dependent on the Collection <> Token model relationship
    def attributes(self):
        cache_key = f"token_attributes_{self.id}"
        if res := cache.get(cache_key):
            return res

        attribute_lookup = self.collection.attribute_lookup()
        if not self.collection.supply or self.collection.supply < 1:
            return []

        attributes = []
        for attr in self.erc721tokenattribute_set.all():
            attr_count = attribute_lookup.get(f"{attr.trait_type}:{attr.value}", None)
            attribute = {
                "trait_type": attr.trait_type,
                "value": attr.value,
                "rarity": min(attr_count / self.collection.supply, 1)
                if attr_count
                else None,
            }
            attributes.append(attribute)
        cache.set(cache_key, attributes, 60 * 15)  # Cache for 15 minutes
        return attributes

    def like_count(self):
        return self.tokenlike_set.count()

    def unique_owners(self):
        if self.smart_contract.type == CollectionType.ERC721:
            return 1
        elif self.smart_contract.type == CollectionType.ERC1155:
            return Erc1155TokenOwner.objects.filter(token=self).count()

    def set_for_sale_info(self, should_save=True):
        sell_order = self.sell_order()
        dutch_auction = self.dutch_auction()

        self.for_sale = bool(sell_order or dutch_auction)
        self.price = None
        self.price_eth = None
        self.payment_token = None
        self.listed_timestamp = None
        self.expiration_timestamp = None

        if sell_order:
            self.price = sell_order.price
            self.price_eth = sell_order.eth_price()
            self.payment_token = sell_order.payment_token
            self.listed_timestamp = sell_order.created_at
            self.expiration_timestamp = sell_order.expiration
        elif dutch_auction:
            dutch_auction.calculate_current_price()
            self.price = dutch_auction.price
            self.price_eth = dutch_auction.eth_price()
            self.payment_token = dutch_auction.payment_token
            self.listed_timestamp = dutch_auction.created_at
            self.expiration_timestamp = dutch_auction.end_time

        if should_save:
            self.save()

    def set_last_price(self, should_save=True):
        sale_order = (
            self.erc721sellorder_set.filter(fulfilled=True)
            .order_by("-time_sold")
            .first()
        )
        buy_order = (
            self.erc721buyorder_set.filter(fulfilled=True)
            .order_by("-time_sold")
            .first()
        )
        dutch_auction = (
            self.erc721dutchauction_set.filter(fulfilled=True)
            .order_by("-time_sold")
            .first()
        )

        last_order = sorted(
            (sale_order, buy_order, dutch_auction),
            reverse=True,
            key=lambda x: x.time_sold
            if x
            else datetime.min.replace(tzinfo=timezone.utc),
        )[0]

        if last_order:
            self.last_sale_price = last_order.price
            self.last_sale_price_eth = last_order.eth_price()
            self.last_sale_payment_token = last_order.payment_token
        else:
            self.last_sale_price = None
            self.last_sale_price_eth = None
            self.last_sale_payment_token = None

        if should_save:
            self.save()

    def set_highest_offer(self, should_save=True):
        buy_orders = self.buy_orders()
        buy_order = buy_orders[0] if buy_orders else None

        if buy_order:
            self.highest_offer = buy_order.price
            self.highest_offer_eth = buy_order.eth_price()
            self.highest_offer_payment_token = buy_order.payment_token
        else:
            self.highest_offer = None
            self.highest_offer_eth = None
            self.highest_offer_payment_token = None

        if should_save:
            self.save()

    def refresh_activity_history(self, hard_pull=False):
        print(f"Pull activity history for {self}")

        if self.smart_contract.type == CollectionType.ERC721:
            contract = Erc721Contract(
                self.smart_contract.address,
                self.smart_contract.network.network_id,
            )
            events = contract.transfer_events_for_token(self.token_id)
        elif self.smart_contract.type == CollectionType.ERC1155:
            contract = Erc1155Contract(
                self.smart_contract.address, self.smart_contract.network.network_id
            )
            single_events = contract.single_transfer_events_for_token(self.token_id)
            batch_events = contract.batch_transfer_events_for_token(self.token_id)
            events = single_events + batch_events

        for event in events:
            txn_id = event["transactionHash"].hex()
            from_address = Web3.toChecksumAddress(event["args"]["from"])
            to_address = Web3.toChecksumAddress(event["args"]["to"])
            quantity = event["args"]["value"] if "value" in event["args"] else 1

            from_profile, _created = Profile.objects.get_or_create(address=from_address)
            to_profile, _created = Profile.objects.get_or_create(address=to_address)

            already_logged = Erc721Activity.objects.filter(
                txn_id=txn_id,
                token=self,
                quantity=quantity,
                from_profile=from_profile,
                to_profile=to_profile,
            ).exists()

            if not already_logged or hard_pull:
                handle_transfer_event(
                    event, network=self.smart_contract.network.network_id
                )

    def pull_media(self, metadata=None, use_existing=False, override_cooldown=False):
        from .utils.metadata_utils import pull_token_media

        return pull_token_media(
            self,
            metadata=metadata,
            use_existing=use_existing,
            override_cooldown=override_cooldown,
        )

    def refresh_owner(self, from_profile=None, to_profile=None, should_save=True):
        if self.smart_contract.type == CollectionType.ERC721:
            contract = Erc721Contract(
                self.smart_contract.address,
                self.smart_contract.network.network_id,
            )
            owner_address = contract.owner_of(self.token_id)
            print(f"Owner address: {owner_address}")
            # Todo: deterime if contract error or Alchemy error first
            if not owner_address:
                owner_address = "0x0000000000000000000000000000000000000000"
            profile, created = Profile.objects.get_or_create(address=owner_address)
            self.owner = profile

            if should_save:
                self.save()
        elif (
                self.smart_contract.type == CollectionType.ERC1155
                and from_profile
                and to_profile
        ):
            try:
                from_erc1155_owner = Erc1155TokenOwner.objects.get(
                    token=self, owner=from_profile
                )
                from_erc1155_owner.refresh_quantity()
            except Erc1155TokenOwner.DoesNotExist:
                pass

            try:
                to_erc1155_owner, created = Erc1155TokenOwner.objects.get_or_create(
                    token=self, owner=to_profile
                )
                to_erc1155_owner.refresh_quantity()
            except Exception as e:
                print(e)

            self.refresh_quantity()

    def refresh_erc1155_owners(self):
        if self.smart_contract.type == CollectionType.ERC1155:
            contract = Erc1155Contract(
                self.smart_contract.address, self.smart_contract.network.network_id
            )
            single_events = contract.single_transfer_events_for_token(self.token_id)
            batch_events = contract.batch_transfer_events_for_token(self.token_id)
            events = single_events + batch_events

            from_addresses = [e["args"]["from"] for e in events]
            to_addresses = [e["args"]["to"] for e in events]
            addresses = list(set(from_addresses + to_addresses))

            for address in addresses:
                if address != "0x0000000000000000000000000000000000000000":
                    profile, created = Profile.objects.get_or_create(address=address)
                    erc1155_owner, created = Erc1155TokenOwner.objects.get_or_create(
                        token=self, owner=profile
                    )
                    erc1155_owner.refresh_quantity()

            self.refresh_quantity()

    def refresh_orders(self, should_save=True):
        # Update sell orders
        sell_orders = Erc721SellOrder.objects.filter(token=self)
        for sell_order in sell_orders:
            sell_order.is_active()

        # Update dutch auctions
        dutch_auctions = Erc721DutchAuction.objects.filter(token=self)
        for dutch_auction in dutch_auctions:
            dutch_auction.is_active()

        # Update buy orders
        buy_orders = Erc721BuyOrder.objects.filter(token=self)
        for buy_order in buy_orders:
            buy_order.is_active()

        # Update order stats
        self.set_for_sale_info(should_save=should_save)
        self.set_last_price(should_save=should_save)
        self.set_highest_offer(should_save=should_save)

    def soft_refresh_orders(self, should_save=True, from_profile=None, to_profile=None):
        sell_orders = Erc721SellOrder.objects.filter(token=self)
        dutch_auctions = Erc721DutchAuction.objects.filter(token=self)
        buy_orders = Erc721BuyOrder.objects.filter(token=self)

        if from_profile and to_profile:
            sell_orders = sell_orders.filter(seller=from_profile)
            dutch_auctions = dutch_auctions.filter(seller=from_profile)
            buy_orders = buy_orders.filter(buyer=to_profile)

        # Update sell orders
        for sell_order in sell_orders:
            sell_order.soft_is_active()

        # Update dutch auctions
        for dutch_auction in dutch_auctions:
            dutch_auction.soft_is_active()

        # Update buy orders
        for buy_order in buy_orders:
            buy_order.soft_is_active()

        # Update order stats
        self.set_for_sale_info(should_save=should_save)
        self.set_last_price(should_save=should_save)
        self.set_highest_offer(should_save=should_save)

    def refresh_quantity(self, should_save=True):
        if self.smart_contract.type == CollectionType.ERC1155:
            try:
                quantity = (
                    Erc1155TokenOwner.objects.filter(token=self)
                    .aggregate(Sum("quantity"))
                    .get("quantity__sum")
                )

                if not quantity:
                    quantity = 0

                self.quantity = quantity

                if should_save:
                    self.save()
            except Exception as e:
                print(e)
                pass

    def refresh_metadata(self, should_save=True):
        from .utils.metadata_utils import refresh_token_metadata

        refresh_token_metadata(self, should_save=should_save)

    # NOTE: This is dependent on the Collection <> Token model relationship
    def refresh_rank(self, should_save=True):
        print(f"Refreshing rank for token #{self.token_id}")
        if (
                self.owner
                and self.owner.address == "0x0000000000000000000000000000000000000000"
        ):
            self.rank = None
        else:
            rarity_lookup = self.collection.rarity_lookup()
            self.rank = rarity_lookup.get(self.token_id)

        if should_save:
            self.save()

    def refresh_token(self):
        print(
            f"Refreshing token {self.smart_contract.collection.name} #{self.token_id}"
        )

        # Refresh owner(s)
        self.refresh_owner(should_save=False)

        # Refresh listing info
        if self.smart_contract.type == CollectionType.ERC721:
            self.refresh_orders(should_save=False)
        else:
            self.soft_refresh_orders(should_save=False)

        # Refresh quantity
        self.refresh_quantity(should_save=False)

        # Set tentative name
        if not self.name:
            if (
                    self.smart_contract.collection.name
                    and len(self.smart_contract.collection.name) > 16
            ):
                default_name = f"#{self.token_id}"
            else:
                default_name = f"{self.smart_contract.collection.name} #{self.token_id}"

            self.name = default_name

        # Refresh metadata
        self.refresh_metadata(should_save=False)

        # Save all changes
        self.save()

        # Refresh actvity history
        if self.smart_contract.type == CollectionType.ERC721:
            self.refresh_activity_history()

    def seo_image(self):
        cache_key = f"SEO_IMAGE_TOKEN_ID_{self.id}"
        if res := cache.get(cache_key):
            return res

        if seo_image := self.collection.seo_image:
            # cache.set(cache_key, seo_image.url, 60 * 60 * 8) # Cache SEO key for 8 hours
            return seo_image.url


class Erc1155TokenOwner(models.Model):
    token = models.ForeignKey(Erc721Token, on_delete=models.PROTECT)
    owner = models.ForeignKey(Profile, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("token", "owner")
        index_together = [
            ("token", "owner"),
        ]

    def refresh_quantity(self):
        contract = Erc1155Contract(
            self.token.smart_contract.address,
            self.token.smart_contract.network.network_id,
        )
        balance = contract.balance_of(self.owner.address, self.token.token_id)
        if balance == 0:
            self.delete()
            return
        else:
            self.quantity = balance

        try:
            self.save()
        except Exception as e:
            print(e)
            pass


class HiddenToken(models.Model):
    user = models.ForeignKey(Profile, on_delete=models.PROTECT)
    token = models.ForeignKey(Erc721Token, on_delete=models.PROTECT)

    class Meta:
        unique_together = ("user", "token")


class FeaturedToken(models.Model):
    user = models.ForeignKey(Profile, on_delete=models.PROTECT)
    token = models.ForeignKey(Erc721Token, on_delete=models.PROTECT)

    class Meta:
        unique_together = ("user", "token")


# TODO: Rename to generic 'TokenAttribute'
class Erc721TokenAttribute(models.Model):
    class Meta:
        verbose_name = "Token attribute"

    token = models.ForeignKey(Erc721Token, on_delete=models.CASCADE)
    trait_type = models.TextField()
    value = models.TextField()


# TODO: Rename to generic 'SellOrder'
class Erc721SellOrder(models.Model):
    class Meta:
        verbose_name = "Sell order"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.ForeignKey(Erc721Token, on_delete=models.PROTECT)
    seller = models.ForeignKey(
        Profile, on_delete=models.PROTECT, related_name="sell_orders"
    )
    start_time = models.DateTimeField(blank=True, null=True)
    expiration = models.DateTimeField()
    price = models.BigIntegerField()  # gwei
    payment_token = models.ForeignKey(
        PaymentToken, on_delete=models.PROTECT, blank=True, null=True
    )
    quantity = models.PositiveIntegerField(default=1)
    created_at_block_number = models.PositiveIntegerField(blank=True, null=True)
    message_hash = models.TextField(blank=True, null=True)
    signature = models.TextField(unique=True)

    # Seaport fields
    order_json = models.TextField(blank=True, null=True)

    # Active status
    cancelled = models.BooleanField(default=False)

    # Sell status
    fulfilled = models.BooleanField(default=False)
    txn_id = models.TextField(blank=True, null=True)
    time_sold = models.DateTimeField(blank=True, null=True)
    buyer = models.ForeignKey(
        Profile,
        on_delete=models.PROTECT,
        related_name="filled_sell_orders",
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    active = models.BooleanField(default=True)

    # Marketplace contract version
    contract_version = models.SmallIntegerField(default=6)

    def __str__(self):
        return f"Sale {self.token}"

    def payment_token_address(self):
        if self.payment_token:
            return self.payment_token.address
        else:
            return None

    def eth_price(self):
        cache_key = f"{self.id}_ETH_PRICE"
        op_to_eth_key = "OP_TO_ETH"
        # if res := cache.get(cache_key):
        #     return res
        try:
            if self.payment_token_id == OP_ID:

                op_to_eth = cache_func(
                    lambda: float(
                        BlockchainState.objects.get(key="op_eth_price").value
                    ),
                    op_to_eth_key,
                    60 * 5,  # Cache for 5 minutes
                )

                price = round(self.price * op_to_eth, 6)
                cache.set(cache_key, price, 60 * 60)  # Cache ETH price for 1 hour
                return price
            else:
                return self.price
        except Exception:
            return self.price

    def usd_price(self):
        eth_to_usd_key = "ETH_TO_USD"
        op_to_usd_key = "OP_TO_USD"
        try:
            if self.payment_token_id == ETH_ID or self.payment_token_id == WETH_ID:
                eth_to_usd = cache_func(
                    lambda: float(
                        BlockchainState.objects.get(key="eth_usd_price").value
                    ),
                    eth_to_usd_key,
                    60 * 5,  # Cache for 5 minutes
                )
                return self.price / 1000000000 * eth_to_usd
            elif self.payment_token_id == OP_ID:
                op_to_usd = cache_func(
                    lambda: float(
                        BlockchainState.objects.get(key="op_usd_price").value
                    ),
                    op_to_usd_key,
                    60 * 5,  # Cache for 5 minutes
                )
                return self.price / 1000000000 * op_to_usd
            else:
                return None
        except Exception:
            return None

    def floor_difference(self):
        try:
            collection_floor = self.token.smart_contract.collection.floor
            difference = (self.eth_price() - collection_floor) / collection_floor * 100
            return difference
        except Exception:
            return None

    def is_active(self):
        self.active = (
                datetime.now(timezone.utc) < self.expiration
                and self.is_owned_by_seller()
                and not self.cancelled
                and not self.fulfilled
                and self.is_active_in_smart_contract()
                and self.is_approved_for_all()
        )

        self.save()

    def soft_is_active(self):
        self.active = (
                datetime.now(timezone.utc) < self.expiration
                and self.is_owned_by_seller()
                and not self.cancelled
                and not self.fulfilled
        )

        self.save()

    def is_owned_by_seller(self):
        if self.seller == self.token.owner:
            return True
        try:
            token_owner = Erc1155TokenOwner.objects.get(
                owner=self.seller, token=self.token
            )
            if token_owner and token_owner.quantity >= self.quantity:
                return True
        except Erc1155TokenOwner.DoesNotExist:
            return False
        return False

    def is_active_in_smart_contract(self):
        if not sell_order_is_active(self):
            self.active = False
            self.cancelled = not self.fulfilled
            self.save()
            return False
        else:
            return True

    def is_approved_for_all(self):
        # This check works for 721s and 1155s because the isApprovedForAll function has the same signature.
        contract = Erc721Contract(
            self.token.smart_contract.address,
            self.token.smart_contract.network.network_id,
        )
        if self.contract_version == 6:
            return contract.is_approved_for_all(
                self.seller.address, EXCHANGE_CONTRACT_V6_ADDRESS
            )

    def save(self, *args, **kwargs):
        return super().save(*args, **kwargs)


# TODO: Rename to generic 'DutchAuction'
class Erc721DutchAuction(models.Model):
    class Meta:
        verbose_name = "Dutch auction"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.ForeignKey(Erc721Token, on_delete=models.PROTECT)
    seller = models.ForeignKey(
        Profile, on_delete=models.PROTECT, related_name="dutch_auctions"
    )
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    start_price = models.BigIntegerField()  # gwei
    end_price = models.BigIntegerField()  # gwei
    payment_token = models.ForeignKey(
        PaymentToken, on_delete=models.PROTECT, blank=True, null=True
    )
    quantity = models.PositiveIntegerField(default=1)
    created_at_block_number = models.PositiveIntegerField(blank=True, null=True)
    message_hash = models.TextField(blank=True, null=True)
    signature = models.TextField(unique=True)

    # Active status
    cancelled = models.BooleanField(default=False)

    # Sell status
    fulfilled = models.BooleanField(default=False)
    txn_id = models.TextField(blank=True, null=True)
    time_sold = models.DateTimeField(blank=True, null=True)
    buyer = models.ForeignKey(
        Profile,
        on_delete=models.PROTECT,
        related_name="filled_dutch_auctions",
        blank=True,
        null=True,
    )
    price = models.BigIntegerField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    active = models.BooleanField(default=True)

    # Marketplace contract version
    contract_version = models.SmallIntegerField(default=6)

    def __str__(self):
        return f"Dutch auction {self.token}"

    def calculate_current_price(self):
        priceDiff = self.start_price - self.end_price
        timeDiff = self.end_time.timestamp() - self.start_time.timestamp()
        timePassed = time.time() - self.start_time.timestamp()
        discount = (priceDiff / timeDiff) * timePassed
        current_price = self.start_price - discount
        self.price = current_price
        self.save()

    def payment_token_address(self):
        if self.payment_token:
            return self.payment_token.address
        else:
            return None

    def eth_price(self):
        try:
            if self.payment_token_id == OP_ID:
                op_to_eth = BlockchainState.objects.get(key="op_eth_price")
                return round(self.price * float(op_to_eth.value), 6)
            else:
                return self.price
        except Exception:
            return self.price

    def usd_price(self):
        try:
            if (
                    self.payment_token.symbol == "ETH"
                    or self.payment_token.symbol == "WETH"
            ):
                eth_to_usd = BlockchainState.objects.get(key="eth_usd_price")
                return self.price / 1000000000 * float(eth_to_usd.value)
            elif self.payment_token.symbol == "OP":
                op_to_usd = BlockchainState.objects.get(key="op_usd_price")
                return self.price / 1000000000 * float(op_to_usd.value)
            else:
                return None
        except Exception:
            return None

    def is_active(self):
        self.active = (
                datetime.now(timezone.utc) < self.end_time
                and self.is_owned_by_seller()
                and not self.cancelled
                and not self.fulfilled
                and self.is_active_in_smart_contract()
        )
        self.save()

    def soft_is_active(self):
        self.active = (
                datetime.now(timezone.utc) < self.end_time
                and self.is_owned_by_seller()
                and not self.cancelled
                and not self.fulfilled
        )
        self.save()

    def is_owned_by_seller(self):
        if self.seller == self.token.owner:
            return True
        try:
            token_owner = Erc1155TokenOwner.objects.get(
                owner=self.seller, token=self.token
            )
            if token_owner and token_owner.quantity >= self.quantity:
                return True
        except Erc1155TokenOwner.DoesNotExist:
            return False
        return False

    def is_active_in_smart_contract(self):
        if not sell_order_is_active(self):
            self.active = False
            self.cancelled = not self.fulfilled
            self.save()
            return False
        else:
            return True

    def save(self, *args, **kwargs):
        return super().save(*args, **kwargs)


# TODO: Rename to generic 'BuyOrder'
class Erc721BuyOrder(models.Model):
    class Meta:
        verbose_name = "Buy order"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.ForeignKey(Erc721Token, on_delete=models.PROTECT)
    seller = models.ForeignKey(
        Profile,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="filled_buy_orders",
    )
    start_time = models.DateTimeField(blank=True, null=True)
    expiration = models.DateTimeField()
    price = models.BigIntegerField()  # gwei
    payment_token = models.ForeignKey(
        PaymentToken, on_delete=models.PROTECT, blank=True, null=True
    )
    quantity = models.PositiveIntegerField(default=1)
    message_hash = models.TextField(blank=True, null=True)
    signature = models.TextField(unique=True)

    # Seaport fields
    order_json = models.TextField(blank=True, null=True)

    # Active status
    cancelled = models.BooleanField(default=False)

    # Sell status
    fulfilled = models.BooleanField(default=False)
    txn_id = models.TextField(blank=True, null=True)
    time_sold = models.DateTimeField(blank=True, null=True)
    buyer = models.ForeignKey(
        Profile, on_delete=models.PROTECT, related_name="buy_orders"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    active = models.BooleanField(default=True)

    # Marketplace contract version
    contract_version = models.SmallIntegerField(default=6)

    def __str__(self):
        return f"Buy order {self.token}"

    def payment_token_address(self):
        if self.payment_token:
            return self.payment_token.address
        else:
            return None

    def eth_price(self):
        try:
            if self.payment_token.symbol == "OP":
                op_to_eth = BlockchainState.objects.get(key="op_eth_price")
                return round(self.price * float(op_to_eth.value), 6)
            else:
                return self.price
        except Exception:
            return self.price

    def usd_price(self):
        try:
            if (
                    self.payment_token.symbol == "ETH"
                    or self.payment_token.symbol == "WETH"
            ):
                eth_to_usd = BlockchainState.objects.get(key="eth_usd_price")
                return self.price / 1000000000 * float(eth_to_usd.value)
            elif self.payment_token.symbol == "OP":
                op_to_usd = BlockchainState.objects.get(key="op_usd_price")
                return self.price / 1000000000 * float(op_to_usd.value)
            else:
                return None
        except Exception:
            return None

    def floor_difference(self):
        try:
            collection_floor = self.token.smart_contract.collection.floor
            difference = (self.eth_price() - collection_floor) / collection_floor * 100
            return difference
        except Exception:
            return None

    def is_active(self):
        self.active = (
                datetime.now(timezone.utc) < self.expiration
                and not self.cancelled
                and not self.fulfilled
                and self.is_active_in_smart_contract()
                and self.has_allowance_and_balance()
        )
        self.save()

    def soft_is_active(self):
        self.active = (
                datetime.now(timezone.utc) < self.expiration
                and not self.cancelled
                and not self.fulfilled
        )
        self.save()

    def is_active_in_smart_contract(self):
        if not order_is_active(self):
            self.active = False
            self.cancelled = not self.fulfilled
            self.save()
            return False
        else:
            return True

    def has_allowance_and_balance(self):
        contract = Erc20Contract(self.payment_token.address)
        if self.contract_version == 6:
            allowance = contract.allowance(
                self.buyer.address, EXCHANGE_CONTRACT_V6_ADDRESS
            )
            balance = contract.balance_of(self.buyer.address)
            price_wei = Web3.toWei(self.price, "gwei")
            return allowance >= price_wei and balance >= price_wei

        return True

    def save(self, *args, **kwargs):
        return super().save(*args, **kwargs)


class ActivityType(models.TextChoices):
    MINT = "MI", _("Mint")
    SALE = "SA", _("Sale")
    TRANSFER = "TR", _("Transfer")
    OFFER = "OF", _("Offer")
    CANCEL_OFFER = "CO", _("Cancel Offer")
    LIST = "LI", _("List")
    CANCEL_LISTING = "CL", _("Cancel Listing")
    AIRDROP = "AD", _("Airdrop")
    BURN = "BU", _("Burn")
    BRIDGE = "BR", _("Bridge")


# TODO: Rename to generic 'OnChainActivity'
class Erc721Activity(models.Model):
    class Meta:
        verbose_name = "On chain activity"
        verbose_name_plural = "On chain activities"
        unique_together = (
            "txn_id",
            "quantity",
            "token",
            "from_profile",
            "to_profile",
            "timestamp",
        )

    txn_id = models.TextField()
    token = models.ForeignKey(Erc721Token, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    sell_order = models.OneToOneField(
        Erc721SellOrder, blank=True, null=True, on_delete=models.SET_NULL
    )
    dutch_auction = models.OneToOneField(
        Erc721DutchAuction, blank=True, null=True, on_delete=models.SET_NULL
    )
    buy_order = models.OneToOneField(
        Erc721BuyOrder, blank=True, null=True, on_delete=models.SET_NULL
    )
    from_profile = models.ForeignKey(
        Profile,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="from_address",
    )
    to_profile = models.ForeignKey(
        Profile, blank=True, null=True, on_delete=models.SET_NULL
    )

    timestamp = models.DateTimeField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    event_type_short = models.CharField(
        max_length=2, choices=ActivityType.choices, null=True, blank=True
    )

    def __str__(self):
        return f"{self.token} {self.event_type()}"

    def event_type(self):
        return self.get_event_type_short_display()

    def refresh_event_type(self, should_save=True):
        if int(self.from_profile.address, 16) == 0:
            if self.token.smart_contract.is_bridged:
                self.event_type_short = ActivityType.BRIDGE
            elif self.token.is_airdrop:
                self.event_type_short = ActivityType.AIRDROP
            else:
                self.event_type_short = ActivityType.MINT
        elif int(self.to_profile.address, 16) == 0:
            if self.token.smart_contract.is_bridged:
                self.event_type_short = ActivityType.BRIDGE
            else:
                self.event_type_short = ActivityType.BURN
        elif self.sell_order or self.buy_order or self.dutch_auction:
            self.event_type_short = ActivityType.SALE
        else:
            if self.to_profile.address== L2ERC721_BRIDGE:
                self.event_type_short = ActivityType.BRIDGE

            else:
                self.event_type_short = ActivityType.TRANSFER

        if should_save:
            self.save()

    def save(self, *args, **kwargs):
        self.refresh_event_type(should_save=False)
        res = super().save(*args, **kwargs)

        if not self.notification_set.all():
            Notification.objects.create(
                profile=self.to_profile,
                token=self.token,
                onchain_activity_id=self.id,
                timestamp=self.timestamp,
            )

            if self.to_profile != self.from_profile:
                Notification.objects.create(
                    profile=self.from_profile,
                    token=self.token,
                    onchain_activity_id=self.id,
                    timestamp=self.timestamp,
                )
        else:
            for notification in self.notification_set.all():
                notification.save()
        return res


class OffChainActivity(models.Model):
    class Meta:
        verbose_name_plural = "Off chain activities"
        unique_together = (
            "token",
            "quantity",
            "from_profile",
            "timestamp",
            "event_type_short",
        )

    txn_id = models.TextField(blank=True, null=True)
    token = models.ForeignKey(Erc721Token, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1, blank=True, null=True)
    sell_order = models.ForeignKey(
        Erc721SellOrder, blank=True, null=True, on_delete=models.SET_NULL
    )
    dutch_auction = models.ForeignKey(
        Erc721DutchAuction, blank=True, null=True, on_delete=models.SET_NULL
    )
    buy_order = models.ForeignKey(
        Erc721BuyOrder, blank=True, null=True, on_delete=models.SET_NULL
    )
    from_profile = models.ForeignKey(
        Profile,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="offchain_activity",
    )
    to_profile = models.ForeignKey(
        Profile, blank=True, null=True, on_delete=models.SET_NULL
    )

    timestamp = models.DateTimeField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    event_type_short = models.CharField(
        max_length=2, choices=ActivityType.choices, null=True, blank=True
    )

    def __str__(self):
        return f"{self.token} {self.event_type()}"

    def event_type(self):
        return self.get_event_type_short_display()


class Notification(models.Model):
    profile = models.ForeignKey(
        Profile, on_delete=models.CASCADE, related_name="notifications"
    )
    token = models.ForeignKey(
        Erc721Token, on_delete=models.CASCADE, blank=True, null=True
    )
    onchain_activity = models.ForeignKey(
        Erc721Activity, on_delete=models.CASCADE, null=True, blank=True
    )
    offchain_activity = models.ForeignKey(
        OffChainActivity, on_delete=models.CASCADE, null=True, blank=True
    )
    timestamp = models.DateTimeField()

    event_type_short = models.CharField(
        max_length=2, choices=ActivityType.choices, null=True, blank=True
    )

    def event_type(self):
        return self.get_event_type_short_display()

    def __str__(self):
        return f"Notification for: {self.profile}"

    def refresh_event_type(self, should_save=True):
        if self.onchain_activity:
            self.event_type_short = self.onchain_activity.event_type_short
        elif self.offchain_activity:
            self.event_type_short = self.offchain_activity.event_type_short

        if should_save:
            self.save()

    def save(self, *args, **kwargs):
        self.refresh_event_type(should_save=False)
        return super().save(*args, **kwargs)

    class Meta:
        unique_together = ("profile", "onchain_activity")


class TokenLike(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
    token = models.ForeignKey(Erc721Token, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("profile", "token")


class FeaturedCollection(models.Model):
    collection = models.ForeignKey(Erc721Collection, on_delete=models.CASCADE)


class SiteBanner(models.Model):
    active = models.BooleanField(default=False)
    message = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.active:
            qs = type(self).objects.filter(active=True)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            qs.update(active=False)
        super(SiteBanner, self).save(*args, **kwargs)


class HostedCollection(models.Model):
    name = models.TextField(null=True)
    address = models.TextField(unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Deprecated Hosted Collection"


class HostedMetadata(models.Model):
    class Meta:
        verbose_name_plural = "Hosted metadata"
        unique_together = ("collection", "token_id")

    collection = models.ForeignKey(HostedCollection, on_delete=models.CASCADE)
    token_id = models.PositiveIntegerField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    animation_url = models.FileField(
        upload_to="quixotic-hosted-collections/animation",
        editable=True,
        blank=True,
        null=False,
        default=None,
    )
    image = models.ImageField(
        upload_to="quixotic-hosted-collections/image",
        editable=True,
        null=True,
        blank=True,
    )
    attributes_str = models.TextField(blank=True, default="{}")
    external_url = models.URLField(blank=True, null=True)

    def name(self):
        return f"{self.collection.name} #{self.token_id}"

    def attributes(self):
        return json.loads(self.attributes_str)

    def __str__(self):
        return f"{self.collection.name} #{self.token_id} ({self.collection.address})"

    class Meta:
        verbose_name = "Deprecated Hosted Collection Metadata"


class BlockchainState(models.Model):
    key = models.TextField(blank=True, null=True, unique=True)
    value = models.TextField(blank=True, null=True)


class ProfileFollow(models.Model):
    class Meta:
        unique_together = ("profile", "followed_collection", "followed_profile")

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
    followed_collection = models.ForeignKey(
        Erc721Collection,
        related_name="followers",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    followed_profile = models.ForeignKey(
        Profile,
        related_name="followers",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )


class NonNFTContract(models.Model):
    class Meta:
        unique_together = ("address", "network")

    address = models.TextField()
    network = models.ForeignKey(Network, on_delete=models.PROTECT, default=1)


class CollectionOfferThreshold(models.Model):
    class Meta:
        unique_together = ("profile", "collection")

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
    collection = models.ForeignKey(Erc721Collection, on_delete=models.CASCADE)
    minimum_offer = models.PositiveBigIntegerField(blank=True, null=True)


class BridgedContract(models.Model):
    class Meta:
        unique_together = ("from_contract", "to_contract")

    approved = models.BooleanField(default=True)
    from_contract = models.ForeignKey(
        Contract, related_name="l2_contract", on_delete=models.PROTECT
    )
    to_contract = models.ForeignKey(
        Contract, related_name="l1_contract", on_delete=models.PROTECT
    )


class RewardsCampaign(models.Model):
    collection = models.OneToOneField(Erc721Collection, on_delete=models.PROTECT)
    is_eligible_for_boost = models.BooleanField(default=False)
    is_boost_active = models.BooleanField(default=False)
    boost_per_mille = models.PositiveSmallIntegerField(blank=True, null=True)
    budget = models.BigIntegerField(blank=True, null=True)
    distributed = models.BigIntegerField(blank=True, null=True)

    def get_layer2_contract_address(self):
        cache_key = f"layer2_contract_address_{self.id}"
        if res := cache.get(cache_key):
            return res

        for contract in self.collection.contract_set.all():
            if not contract.is_layer1():
                l2_addr = contract.address
                cache.set(cache_key, l2_addr, 60 * 60 * 12)  # Cache result for 12 hours
                return l2_addr

    def refresh_campaign(self):
        l2_addr = self.get_layer2_contract_address()

        self.is_eligible_for_boost = is_eligible_for_boost(l2_addr)
        self.is_boost_active = is_campaign_active(l2_addr)
        self.boost_per_mille = get_boost_per_mille(l2_addr)
        self.budget = get_budget(l2_addr)
        new_distributed = get_amount_distributed(l2_addr)

        if (
                self.distributed
                and self.distributed > 0
                and (new_distributed - self.distributed) >= 250
        ):
            send_email_about_campaign_distribution(self)

        self.distributed = new_distributed

        if (
                self.budget
                and self.distributed
                and self.budget > 0
                and (self.distributed / self.budget) > 0.5
                and (self.budget - self.distributed) < 500
                and self.collection.address
        ):
            send_email_about_campaign_budget(self)

        self.save()
