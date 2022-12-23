from django.contrib import admin
from batch_processing.tasks.token.tasks import refresh_token as queue_refresh_token

import os
from . import models


@admin.action(description="Refresh Collection")
def refresh_collection(modeladmin, request, queryset):
    for e in queryset:
        e.refresh_collection()


@admin.action(description="Refresh Contract")
def refresh_contract(modeladmin, request, queryset):
    for e in queryset:
        e.refresh_contract()


@admin.action(description="Refresh Token")
def refresh_token(modeladmin, request, queryset):
    for e in queryset:
        e.refresh_token()


@admin.action(description="Refresh Stats")
def refresh_collection_stats(modeladmin, request, queryset):
    for e in queryset:
        e.refresh_stats()


@admin.action(description="Refresh Campaign")
def refresh_campaign(modeladmin, request, queryset):
    for e in queryset:
        e.refresh_campaign()


@admin.action(description="Pull Media into AWS")
def pull_media(modeladmin, request, queryset):
    for e in queryset:
        e.pull_media(override_cooldown=True)


@admin.action(description="Refresh ENS")
def refresh_ens(modeladmin, request, queryset):
    for e in queryset:
        e.refresh_ens()


@admin.action(description="Refresh Activity History")
def refresh_activity_history(modeladmin, request, queryset):
    for e in queryset:
        e.refresh_activity_history(hard_pull=True)


@admin.action(description="Pull New Tokens")
def pull_new_tokens(modeladmin, request, queryset):
    for e in queryset:
        e.pull_new_tokens()


@admin.action(description="Refresh Owner(s)")
def refresh_owners(modeladmin, request, queryset):
    for e in queryset:
        e.refresh_owner()
        e.refresh_erc1155_owners()


@admin.action(description="Refresh Orders")
def refresh_orders(modeladmin, request, queryset):
    for e in queryset:
        e.refresh_orders()


@admin.action(description="Refresh Metadata")
def refresh_metadata(modeladmin, request, queryset):
    for e in queryset:
        e.refresh_metadata()


@admin.action(description="Refresh Rarity Ranks")
def refresh_ranks(modeladmin, request, queryset):
    for e in queryset:
        e.refresh_ranks()

@admin.action(description="Batch refresh tokens")
def batch_refresh_tokens(modeladmin, request, queryset):
    for collection in queryset:
        for token in collection.erc721token_set.all():
            if os.environ.get("USE_CELERY"):
                queue_refresh_token.apply_async((token.id,), queue="refresh_token")
            else:
                token.refresh_token()

@admin.register(models.Erc721Collection)
class CollectionAdmin(admin.ModelAdmin):
    search_fields = ["name", "address"]
    readonly_fields = [
        "id",
        "symbol",
        "owner",
        "floor",
        "volume",
        "volume_24h",
        "volume_7d",
        "volume_30d",
        "volume_prev_24h",
        "volume_prev_7d",
        "volume_prev_30d",
        "sales",
        "sales_24h",
        "sales_7d",
        "sales_30d",
        "supply",
        "listed",
        "owners",
        "l1_address",
        "total_supply",
        "is_eligible_for_boost",
        "is_boost_active",
    ]
    raw_id_fields = ["primary_contract"]
    list_display = [
        "__str__",
        "id",
        "address",
        "network",
        "type",
        "supply",
        "verified",
        "delisted",
        "is_spam",
        "approved",
    ]
    list_editable = ["approved", "verified", "delisted", "is_spam"]
    actions = [
        refresh_collection,
        refresh_metadata,
        refresh_collection_stats,
        refresh_ranks,
        batch_refresh_tokens
    ]


@admin.register(models.Contract)
class ContractAdmin(admin.ModelAdmin):
    search_fields = ["name", "address"]
    readonly_fields = ["id", "symbol", "owner"]
    raw_id_fields = ["collection"]
    list_display = [
        "address",
        "name",
        "network",
        "type",
        "total_supply",
        "approved",
    ]
    list_editable = ["approved"]
    actions = [
        refresh_contract,
        pull_new_tokens,
    ]


class TokenAttributeInline(admin.TabularInline):
    model = models.Erc721TokenAttribute
    readonly_fields = ["trait_type", "value"]


@admin.register(models.Erc721Token)
class TokenAdmin(admin.ModelAdmin):
    search_fields = ["name"]
    readonly_fields = [
        "id",
        "token_id",
        "name",
        "collection",
        "smart_contract",
        "pending_owner",
        "owner",
        "quantity",
        "external_url",
        "background_color",
        "last_media_pull",
        "for_sale",
        "price",
        "last_sale_price",
        "highest_offer",
        "listed_timestamp",
        "expiration_timestamp",
    ]
    list_display = ["name", "id", "collection", "token_id", "approved"]
    list_editable = ["approved"]

    actions = [
        refresh_token,
        refresh_activity_history,
        pull_media,
        refresh_owners,
        refresh_orders,
        refresh_metadata,
    ]
    inlines = [TokenAttributeInline]

    list_filter = [
        ["collection", admin.RelatedOnlyFieldListFilter],
    ]

    list_per_page = 50


@admin.register(models.Erc721SellOrder)
class SellOrderAdmin(admin.ModelAdmin):
    readonly_fields = ["id", "token", "contract_version", "seller", "buyer"]
    search_fields = ["token__name", "txn_id"]
    list_display = [
        "token",
        "active",
        "fulfilled",
        "contract_version",
        "created_at",
        "expiration",
    ]
    ordering = ("-created_at",)

    list_filter = [
        ["fulfilled", admin.BooleanFieldListFilter],
    ]


@admin.register(models.Erc721BuyOrder)
class BuyOrderAdmin(admin.ModelAdmin):
    readonly_fields = ["id", "token", "contract_version", "seller", "buyer"]
    search_fields = ["token__name", "txn_id"]
    list_display = [
        "token",
        "active",
        "fulfilled",
        "contract_version",
        "created_at",
        "expiration",
    ]
    ordering = ("-created_at",)

    list_filter = [
        ["fulfilled", admin.BooleanFieldListFilter],
    ]


@admin.register(models.Erc721DutchAuction)
class DutchAuctionAdmin(admin.ModelAdmin):
    readonly_fields = ["id", "token", "seller", "buyer"]
    search_fields = ["token__name", "txn_id"]
    list_display = [
        "token",
        "active",
        "fulfilled",
        "contract_version",
        "created_at",
        "end_time",
    ]
    ordering = ("-created_at",)

    list_filter = [
        ["fulfilled", admin.BooleanFieldListFilter],
    ]


@admin.register(models.Network)
class NetworkAdmin(admin.ModelAdmin):
    search_fields = ["name", "network", "network_id", "chain_id"]
    list_display = ["name", "network_id", "chain_id"]


@admin.register(models.PaymentToken)
class PaymentTokenAdmin(admin.ModelAdmin):
    search_fields = ["address", "name", "symbol"]
    list_display = ["address", "name", "symbol"]


@admin.register(models.Profile)
class ProfileAdmin(admin.ModelAdmin):
    search_fields = ["address", "reverse_ens", "username"]
    list_display = ["address", "reverse_ens", "username"]
    actions = [refresh_ens]


# @admin.register(models.ProfileFollow)
# class ProfileFollowAdmin(admin.ModelAdmin):
#     list_display = ["profile", "followed_collection", "followed_profile"]
#     raw_id_fields = ["profile", "followed_collection", "followed_profile"]


@admin.register(models.Erc721Activity)
class OnChainActivityAdmin(admin.ModelAdmin):
    search_fields = ["from_profile__address", "to_profile__address", "txn_id"]
    list_display = ["__str__", "event_type", "from_profile", "to_profile", "timestamp"]
    readonly_fields = [
        "token",
        "sell_order",
        "buy_order",
        "dutch_auction",
        "from_profile",
        "to_profile",
    ]


@admin.register(models.OffChainActivity)
class OffChainActivityAdmin(admin.ModelAdmin):
    list_display = ["__str__", "event_type", "from_profile", "to_profile", "timestamp"]
    readonly_fields = [
        "token",
        "sell_order",
        "buy_order",
        "dutch_auction",
        "from_profile",
        "to_profile",
    ]


# @admin.register(models.Notification)
# class NotificationAdmin(admin.ModelAdmin):
#     list_display = ["__str__", "onchain_activity", "offchain_activity", "event_type"]
#     readonly_fields = ["token", "profile", "onchain_activity", "offchain_activity"]


# @admin.register(models.TokenLike)
# class TokenLikeAdmin(admin.ModelAdmin):
#     list_display = ["token", "profile"]


@admin.register(models.FeaturedCollection)
class FeaturedCollectionAdmin(admin.ModelAdmin):
    list_display = ["collection"]
    raw_id_fields = ["collection"]


@admin.register(models.SiteBanner)
class SiteBannerAdmin(admin.ModelAdmin):
    list_display = ["message", "active"]
    list_editable = ["active"]


@admin.register(models.NonNFTContract)
class NonNFTContractAdmin(admin.ModelAdmin):
    search_fields = ["address"]
    list_display = ["address"]


# @admin.register(models.HostedCollection)
# class HostedCollectionAdmin(admin.ModelAdmin):
#     pass


# @admin.register(models.HostedMetadata)
# class HostedMetadataAdmin(admin.ModelAdmin):
#     pass


@admin.register(models.Erc1155TokenOwner)
class Erc1155TokenOwnerAdmin(admin.ModelAdmin):
    list_display = ["token", "owner", "quantity"]
    readonly_fields = ["token", "owner"]


# @admin.register(models.HiddenToken)
# class HiddenTokenAdmin(admin.ModelAdmin):
#     list_display = ["token", "user"]
#     readonly_fields = ["token", "user"]


# @admin.register(models.FeaturedToken)
# class FeaturedToken(admin.ModelAdmin):
#     list_display = ["token", "user"]
#     readonly_fields = ["token", "user"]


@admin.register(models.BlockchainState)
class BlockchainStateAdmin(admin.ModelAdmin):
    list_display = ["key", "value"]


@admin.register(models.BridgedContract)
class BridgedContractAdmin(admin.ModelAdmin):
    list_display = ["from_contract", "to_contract", "approved"]
    list_editable = ["approved"]
    raw_id_fields = ["from_contract", "to_contract"]


@admin.register(models.RewardsCampaign)
class RewardsCampaignAdmin(admin.ModelAdmin):
    list_display = [
        "collection",
        "boost_per_mille",
        "budget",
        "distributed",
        "is_eligible_for_boost",
        "is_boost_active",
    ]
    raw_id_fields = ["collection"]
    actions = [
        refresh_campaign,
    ]
