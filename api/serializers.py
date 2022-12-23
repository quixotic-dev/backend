from rest_framework import serializers

from . import fields, models


class ProfileSerializerMini(serializers.ModelSerializer):
    class Meta:
        model = models.Profile
        fields = ["address"]


class ProfileSerializerShort(serializers.ModelSerializer):
    class Meta:
        model = models.Profile
        fields = ["address", "username", "reverse_ens", "profile_image"]


class RewardsCampaignSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.RewardsCampaign
        fields = [
            "is_eligible_for_boost",
            "is_boost_active",
            "boost_per_mille",
            "budget",
            "distributed",
        ]


class CollectionSerializer(serializers.ModelSerializer):
    owner = ProfileSerializerShort()
    rewardscampaign = RewardsCampaignSerializer()

    class Meta:
        model = models.Erc721Collection
        fields = [
            "id",
            "blockchain",
            "address",
            "name",
            "symbol",
            "owner",
            "supply",
            "owners",
            "floor",
            "listed",
            "sales",
            "volume",
            "royalty_per_mille",
            "payout_address",
            "verified",
            "is_spam",
            "delisted",
            "non_transferable",
            "cover_image",
            "slug",
            "description",
            "twitter_link",
            "discord_link",
            "site_link",
            "display_theme",
            "contract_type",
            "default_sort_str",
            "animation_url_type",
            "image_url",
            "ranking_enabled",
            "rewardscampaign",
        ]


class CollectionAttributesSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Erc721Collection
        fields = [
            "address",
            "attributes",
        ]


class CollectionSerializerForStats(serializers.ModelSerializer):
    class Meta:
        model = models.Erc721Collection
        fields = [
            "id",
            "blockchain",
            "address",
            "name",
            "supply",
            "owners",
            "floor",
            "listed",
            "sales",
            "volume",
            "verified",
            "slug",
            "volume_change_24h",
            "volume_change_7d",
            "image_url",
            "eth_to_usd",
        ]


class CollectionSerializerForStats24H(CollectionSerializerForStats):
    volume = serializers.IntegerField(source="volume_24h")
    sales = serializers.IntegerField(source="sales_24h")


class CollectionSerializerForStats7D(CollectionSerializerForStats):
    volume = serializers.IntegerField(source="volume_7d")
    sales = serializers.IntegerField(source="sales_7d")


class CollectionSerializerForStats30D(CollectionSerializerForStats):
    volume = serializers.IntegerField(source="volume_30d")
    sales = serializers.IntegerField(source="sales_30d")


class CollectionSerializerShort(serializers.ModelSerializer):
    class Meta:
        model = models.Erc721Collection
        fields = ["address"]


class PaymentTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PaymentToken
        fields = ["address", "name", "symbol"]


class SellOrderSerializerShort(serializers.ModelSerializer):
    seller = ProfileSerializerShort()
    payment_token = PaymentTokenSerializer()

    class Meta:
        model = models.Erc721SellOrder
        fields = [
            "id",
            "start_time",
            "expiration",
            "price",
            "eth_price",
            "usd_price",
            "quantity",
            "seller",
            "contract_version",
            "active",
            "cancelled",
            "fulfilled",
            "payment_token",
        ]


class BuyOrderSerializerShort(serializers.ModelSerializer):
    buyer = ProfileSerializerShort()
    payment_token = PaymentTokenSerializer()

    class Meta:
        model = models.Erc721BuyOrder
        fields = [
            "id",
            "start_time",
            "expiration",
            "price",
            "eth_price",
            "usd_price",
            "quantity",
            "buyer",
            "contract_version",
            "active",
            "cancelled",
            "fulfilled",
            "payment_token",
            "floor_difference",
        ]


class DutchAuctionSerializerShort(serializers.ModelSerializer):
    seller = ProfileSerializerShort()
    payment_token = PaymentTokenSerializer()

    class Meta:
        model = models.Erc721DutchAuction
        fields = [
            "id",
            "start_time",
            "end_time",
            "start_price",
            "end_price",
            "price",
            "eth_price",
            "usd_price",
            "quantity",
            "seller",
            "contract_version",
            "active",
            "cancelled",
            "fulfilled",
            "payment_token",
        ]


class CollectionSerializerMedium(serializers.ModelSerializer):
    rewardscampaign = RewardsCampaignSerializer()

    class Meta:
        model = models.Erc721Collection
        fields = [
            "blockchain",
            "address",
            "name",
            "verified",
            "is_spam",
            "delisted",
            "non_transferable",
            "description",
            "slug",
            "supply",
            "owners",
            "floor",
            "listed",
            "volume",
            "display_theme",
            "contract_type",
            "image_url",
            "cover_image",
            "ranking_enabled",
            "volume_change_7d",
            "rewardscampaign",
        ]


class CollectionSerializerForToken(serializers.ModelSerializer):
    owner = ProfileSerializerShort()
    payment_tokens = PaymentTokenSerializer(many=True)

    class Meta:
        model = models.Erc721Collection
        fields = [
            "address",
            "name",
            "symbol",
            "owner",
            "verified",
            "is_spam",
            "delisted",
            "non_transferable",
            "slug",
            "display_theme",
            "animation_url_type",
            "contract_type",
            "image_url",
            "ranking_enabled",
            "twitter_link",
            "discord_link",
            "site_link",
            "royalty_per_mille",
            "payout_address",
            "payment_tokens",
            "floor_price",
        ]


class CollectionSerializerForSettings(serializers.ModelSerializer):
    owner = ProfileSerializerShort()
    rewardscampaign = RewardsCampaignSerializer()

    class Meta:
        model = models.Erc721Collection
        fields = [
            "address",
            "name",
            "symbol",
            "owner",
            "category",
            "categories",
            "royalty_per_mille",
            "payout_address",
            "profile_image",
            "cover_image",
            "slug",
            "description",
            "twitter_link",
            "discord_link",
            "site_link",
            "display_theme",
            "ranking_enabled",
            "rewardscampaign",
        ]


class TokenLikeSerializerShort(serializers.ModelSerializer):
    profile = ProfileSerializerMini()

    class Meta:
        model = models.TokenLike
        fields = ["profile"]


class TokenSerializerForCollectionTokens(serializers.ModelSerializer):
    collection = serializers.SerializerMethodField()
    sell_order = SellOrderSerializerShort()
    dutch_auction = serializers.SerializerMethodField()
    owner = ProfileSerializerShort()
    last_sale_payment_token = PaymentTokenSerializer()
    highest_offer_payment_token = PaymentTokenSerializer()

    class Meta:
        model = models.Erc721Token
        fields = [
            "collection",
            "token_id",
            "name",
            "owner",
            "description",
            "image",
            "animation_url",
            "sell_order",
            "dutch_auction",
            "last_sale_price",
            "last_sale_payment_token",
            "highest_offer",
            "highest_offer_payment_token",
            "background_color",
            "unique_owners",
            "rank",
            "contract_address",
            "network",
            "bridged",
        ]

    def get_collection(self, obj):
        return self.context.get("collection_ctx")

    def get_dutch_auction(self, obj):
        return None


class TokenSerializerMedium(serializers.ModelSerializer):
    collection = CollectionSerializerForToken()
    sell_order = SellOrderSerializerShort()
    dutch_auction = DutchAuctionSerializerShort()
    owner = ProfileSerializerShort()
    last_sale_payment_token = PaymentTokenSerializer()
    highest_offer_payment_token = PaymentTokenSerializer()

    class Meta:
        model = models.Erc721Token
        fields = [
            "collection",
            "token_id",
            "name",
            "owner",
            "description",
            "image",
            "animation_url",
            "sell_order",
            "dutch_auction",
            "last_sale_price",
            "last_sale_payment_token",
            "highest_offer",
            "highest_offer_payment_token",
            "background_color",
            "unique_owners",
            "rank",
            "contract_address",
            "network",
            "bridged",
        ]


class CollectionSerializerForTokenCard(serializers.ModelSerializer):
    class Meta:
        model = models.Erc721Collection
        fields = [
            "address",
            "name",
            "symbol",
            "verified",
            "slug",
            "display_theme",
            "animation_url_type",
            "contract_type",
            "image_url",
            "ranking_enabled",
        ]


class TokenSerializerForProfile(serializers.ModelSerializer):
    collection = CollectionSerializerForTokenCard()
    sell_order = SellOrderSerializerShort()
    owner = serializers.SerializerMethodField()
    dutch_auction = serializers.SerializerMethodField()
    last_sale_payment_token = PaymentTokenSerializer()
    highest_offer_payment_token = PaymentTokenSerializer()

    class Meta:
        model = models.Erc721Token
        fields = [
            "collection",
            "token_id",
            "name",
            "owner",
            "description",
            "image",
            "animation_url",
            "sell_order",
            "dutch_auction",
            # "price",
            "last_sale_price",
            "last_sale_payment_token",
            "highest_offer",
            "highest_offer_payment_token",
            "background_color",
            "unique_owners",
            "rank",
            "contract_address",
            "network",
            "bridged",
        ]

    def get_owner(self, obj):
        return {"address": self.context.get("owner_ctx")}

    def get_dutch_auction(self, obj):
        return None


class OnChainActivitySerializerShort(serializers.ModelSerializer):
    sell_order = SellOrderSerializerShort()
    buy_order = BuyOrderSerializerShort()
    dutch_auction = DutchAuctionSerializerShort()
    from_profile = ProfileSerializerShort()
    to_profile = ProfileSerializerShort()

    class Meta:
        model = models.Erc721Activity
        fields = [
            "__str__",
            "txn_id",
            "from_profile",
            "to_profile",
            "sell_order",
            "buy_order",
            "dutch_auction",
            "timestamp",
            "event_type",
        ]


class OnChainActivitySerializer(serializers.ModelSerializer):
    sell_order = SellOrderSerializerShort()
    buy_order = BuyOrderSerializerShort()
    dutch_auction = DutchAuctionSerializerShort()
    from_profile = ProfileSerializerShort()
    to_profile = ProfileSerializerShort()
    token = TokenSerializerMedium()

    class Meta:
        model = models.Erc721Activity
        fields = [
            "__str__",
            "txn_id",
            "from_profile",
            "to_profile",
            "sell_order",
            "buy_order",
            "dutch_auction",
            "timestamp",
            "event_type",
            "token",
        ]


class OffChainActivitySerializerShort(serializers.ModelSerializer):
    sell_order = SellOrderSerializerShort()
    buy_order = BuyOrderSerializerShort()
    dutch_auction = DutchAuctionSerializerShort()
    from_profile = ProfileSerializerShort()

    class Meta:
        model = models.Erc721Activity
        fields = [
            "__str__",
            "from_profile",
            "sell_order",
            "buy_order",
            "dutch_auction",
            "timestamp",
            "event_type",
        ]


class OffChainActivitySerializer(serializers.ModelSerializer):
    sell_order = SellOrderSerializerShort()
    buy_order = BuyOrderSerializerShort()
    dutch_auction = DutchAuctionSerializerShort()
    from_profile = ProfileSerializerShort()
    token = TokenSerializerMedium()

    class Meta:
        model = models.Erc721Activity
        fields = [
            "__str__",
            "from_profile",
            "sell_order",
            "buy_order",
            "dutch_auction",
            "timestamp",
            "event_type",
            "token",
        ]


class TokenSerializer(serializers.ModelSerializer):
    collection = CollectionSerializerForToken()
    owner = ProfileSerializerShort()
    pending_owner = ProfileSerializerShort()
    sell_order = SellOrderSerializerShort()
    dutch_auction = DutchAuctionSerializerShort()
    buy_order = BuyOrderSerializerShort()
    sell_orders = SellOrderSerializerShort(many=True)
    dutch_auctions = DutchAuctionSerializerShort(many=True)
    buy_orders = BuyOrderSerializerShort(many=True)
    last_sale_payment_token = PaymentTokenSerializer()
    highest_offer_payment_token = PaymentTokenSerializer()

    class Meta:
        model = models.Erc721Token
        fields = [
            "collection",
            "token_id",
            "name",
            "description",
            "image",
            "animation_url",
            "owner",
            "pending_owner",
            "pending_deposit",
            "sell_order",
            "dutch_auction",
            "buy_order",
            "sell_orders",
            "dutch_auctions",
            "buy_orders",
            "price_history",
            "attributes",
            "like_count",
            "last_sale_price",
            "last_sale_payment_token",
            "highest_offer",
            "highest_offer_payment_token",
            "background_color",
            "external_url",
            "quantity",
            "unique_owners",
            "rank",
            "minimum_offer",
            "contract_address",
            "network",
            "bridged",
            "seo_image"
        ]


class TokenSerializerShort(serializers.ModelSerializer):
    collection = CollectionSerializerShort()

    class Meta:
        model = models.Erc721Token
        fields = ["collection", "token_id"]


class TokenLikeSerializerForProfile(serializers.ModelSerializer):
    token = TokenSerializerShort()

    class Meta:
        model = models.TokenLike
        fields = ["token"]


class TokenLikeSerializer(serializers.ModelSerializer):
    profile = serializers.StringRelatedField()
    token = TokenSerializerMedium()

    class Meta:
        model = models.TokenLike
        fields = ["profile", "token"]


class ProfileSerializer(serializers.ModelSerializer):
    likes = TokenLikeSerializerForProfile(many=True)

    class Meta:
        model = models.Profile
        fields = [
            "address",
            "username",
            "reverse_ens",
            "profile_image",
            "cover_image",
            "bio",
            "twitter",
            "likes",
            "followed_collections",
            "followed_profiles",
        ]


class ProfileSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Profile
        fields = [
            "address",
            "username",
            "reverse_ens",
            "profile_image",
            "cover_image",
            "bio",
            "email",
            "twitter",
            "minimum_offer",
        ]


class Erc1155TokenOwnerSerializer(serializers.ModelSerializer):
    token = TokenSerializerShort()
    owner = ProfileSerializer()

    class Meta:
        model = models.Erc1155TokenOwner
        fields = ["token", "owner", "quantity"]


class Erc1155TokenOwnerSerializerShort(serializers.ModelSerializer):
    owner = ProfileSerializer()

    class Meta:
        model = models.Erc1155TokenOwner
        fields = ["owner", "quantity"]


class SellOrderSerializer(serializers.ModelSerializer):
    token = TokenSerializerMedium()
    seller = ProfileSerializerShort()
    start_time = fields.TimestampField()
    expiration = fields.TimestampField()
    payment_token = PaymentTokenSerializer()

    class Meta:
        model = models.Erc721SellOrder
        fields = [
            "seller",
            "token",
            "start_time",
            "expiration",
            "price",
            "usd_price",
            "floor_difference",
            "quantity",
            "created_at_block_number",
            "signature",
            "active",
            "cancelled",
            "fulfilled",
            "contract_version",
            "payment_token",
            "payment_token_address",
            "order_json",
        ]


class BuyOrderSerializer(serializers.ModelSerializer):
    token = TokenSerializerMedium()
    buyer = ProfileSerializerShort()
    payment_token = PaymentTokenSerializer()

    class Meta:
        model = models.Erc721BuyOrder
        fields = [
            "id",
            "buyer",
            "token",
            "start_time",
            "expiration",
            "price",
            "usd_price",
            "quantity",
            "signature",
            "active",
            "cancelled",
            "fulfilled",
            "contract_version",
            "payment_token",
            "payment_token_address",
            "order_json",
            "floor_difference",
        ]


class DutchAuctionSerializer(serializers.ModelSerializer):
    token = TokenSerializerShort()
    seller = ProfileSerializerShort()
    start_time = fields.TimestampField()
    end_time = fields.TimestampField()
    payment_token = PaymentTokenSerializer()

    class Meta:
        model = models.Erc721DutchAuction
        fields = [
            "seller",
            "token",
            "start_time",
            "end_time",
            "start_price",
            "end_price",
            "quantity",
            "created_at_block_number",
            "price",
            "usd_price",
            "signature",
            "active",
            "cancelled",
            "fulfilled",
            "contract_version",
            "payment_token",
            "payment_token_address",
        ]


class SiteBannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.SiteBanner

        fields = ["active", "message"]


class CollectionSerializerForNotification(serializers.ModelSerializer):
    class Meta:
        model = models.Erc721Collection
        fields = [
            "address",
        ]


class TokenSerializerForNotification(serializers.ModelSerializer):
    collection = CollectionSerializerForNotification()

    class Meta:
        model = models.Erc721Token
        fields = [
            "collection",
            "network",
            "contract_address",
            "token_id",
            "name",
            "image",
        ]


class OnChainActivitySerializerForNotification(serializers.ModelSerializer):
    from_profile = ProfileSerializerShort()
    to_profile = ProfileSerializerShort()

    class Meta:
        model = models.Erc721Activity
        fields = [
            "__str__",
            "txn_id",
            "from_profile",
            "to_profile",
            "timestamp",
            "event_type",
        ]


class NotificationSerializer(serializers.ModelSerializer):
    token = TokenSerializerForNotification()
    onchain_activity = OnChainActivitySerializerForNotification()
    offchain_activity = OffChainActivitySerializerShort()

    class Meta:
        model = models.Notification

        fields = [
            "event_type",
            "token",
            "onchain_activity",
            "offchain_activity",
            "timestamp",
        ]


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


class ProfileSerializerForSearch(serializers.ModelSerializer):
    class Meta:
        model = models.Profile
        fields = [
            "address",
            "username",
            "reverse_ens",
            "profile_image",
        ]


class CollectionSerializerForSearch(serializers.ModelSerializer):
    class Meta:
        model = models.Erc721Collection
        fields = [
            "name",
            "blockchain",
            "address",
            "slug",
            "image_url",
            "supply",
            "verified",
        ]


class CollectionSerializerForThreshold(serializers.ModelSerializer):
    class Meta:
        model = models.Erc721Collection
        fields = [
            "address",
            "name",
            "verified",
            "slug",
            "supply",
            "floor",
            "contract_type",
            "image_url",
        ]


class CollectionOfferThresholdSerializer(serializers.ModelSerializer):
    collection = CollectionSerializerForThreshold()

    class Meta:
        model = models.CollectionOfferThreshold
        fields = ["collection", "minimum_offer"]
