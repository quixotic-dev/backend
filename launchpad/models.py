from django.db import models
import os
import json
from web3 import Web3
import eth_account

from launchpad.utils.LaunchpadContract import LaunchpadContract

BOUNCER_PRIVATE_KEY = os.environ.get("BOUNCER_PRIVATE_KEY")


class HostedCollection(models.Model):
    name = models.TextField(blank=True, null=True)
    address = models.TextField(unique=True)
    src_code = models.TextField(blank=True, null=True)
    max_supply = models.PositiveIntegerField(blank=True, null=True)
    premint_price = models.BigIntegerField(blank=True, null=True)
    mint_price = models.BigIntegerField(blank=True, null=True)
    max_per_premint = models.PositiveIntegerField(default=1)
    max_per_mint = models.PositiveIntegerField(default=1)
    premint = models.BooleanField(default=False)
    premint_enabled = models.BooleanField(default=False)
    mint_enabled = models.BooleanField(default=False)
    metadata_generated = models.BooleanField(default=False)
    base_uri = models.URLField(blank=True, null=True)
    base_uri_token_id = models.BooleanField(default=True)
    base_uri_file_extension = models.BooleanField(default=True)
    reserve_tokens = models.BooleanField(default=False)
    featured = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} (ID: {self.id})" if self.name else f"Internal ID: {self.id}"

    def greenlist_count(self):
        return GreenlistedAddress.objects.filter(collection=self).count()

    def refresh(self):
        contract = LaunchpadContract(self.address)

        try:
            self.premint_enabled = contract.premint_state()
        except Exception:
            print("Could not refresh contract premint state")

        try:
            self.mint_enabled = contract.mint_state()
        except Exception:
            print("Could not refresh contract mint state")

        self.save()


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
    active = models.BooleanField(default=False)

    def name(self):
        return f"{self.collection.name} #{self.token_id}"

    def attributes(self):
        return json.loads(self.attributes_str)

    def refresh(self):
        contract = LaunchpadContract(self.collection.address)

        try:
            contract.token_by_index(self.token_id)
            self.active = True
        except Exception:
            print("Token does not exist")

        self.save()

    def __str__(self):
        return f"{self.collection.name} #{self.token_id} ({self.collection.address})"


class GreenlistedAddress(models.Model):
    collection = models.ForeignKey(HostedCollection, on_delete=models.CASCADE)
    address = models.CharField(max_length=42)

    def get_signature(self):
        raw_msg = Web3.solidityKeccak(["address"], [self.address])
        encoded_msg = eth_account.messages.encode_defunct(raw_msg)
        acct = eth_account.Account.from_key(BOUNCER_PRIVATE_KEY)
        sig = acct.sign_message(encoded_msg).signature.hex()
        print(sig)
        return sig

    def __str__(self):
        return f"{self.address}"

    class Meta:
        unique_together = ("collection", "address")
