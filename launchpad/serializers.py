from rest_framework import serializers

from . import models


class HostedMetadataSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="token_id")

    class Meta:
        model = models.HostedMetadata
        fields = [
            "id",
            "name",
            "description",
            "image",
            "animation_url",
            "external_url",
            "attributes",
        ]


class HostedCollectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.HostedCollection
        fields = [
            "name",
            "address",
            "max_supply",
            "premint_price",
            "mint_price",
            "max_per_premint",
            "max_per_mint",
            "premint_enabled",
            "mint_enabled",
            "premint",
            "metadata_generated",
            "base_uri",
            "greenlist_count",
            "base_uri_token_id",
            "base_uri_file_extension",
            "reserve_tokens",
            "src_code",
        ]


class GreenlistedAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.GreenlistedAddress
        fields = ["address"]
