from api import fields, models
from rest_framework import serializers


class PublicAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Profile
        fields = [
            "address",
            "username",
        ]


class PublicCollectionSerializer(serializers.ModelSerializer):
    external_link = serializers.URLField(source="site_link")
    image_url = serializers.SerializerMethodField()
    banner_image_url = serializers.ImageField(source="cover_image")
    owner = PublicAccountSerializer()
    traits = serializers.ListField(source="attributes")
    floor_price = serializers.IntegerField(source="floor")
    volume_traded = serializers.IntegerField(source="volume")

    class Meta:
        model = models.Erc721Collection
        fields = [
            "address",
            "name",
            "symbol",
            "contract_type",
            "external_link",
            "description",
            "slug",
            "image_url",
            "banner_image_url",
            "royalty_per_mille",
            "payout_address",
            "verified",
            "traits",
            "owner",
            "floor_price",
            "volume_traded",
        ]

    def get_image_url(self, instance):
        if instance.profile_image:
            return instance.profile_image.url
        else:
            return instance.profile_image_url


class PublicCollectionSerializerMedium(serializers.ModelSerializer):
    external_link = serializers.URLField(source="site_link")
    image_url = serializers.SerializerMethodField()
    banner_image_url = serializers.ImageField(source="cover_image")
    owner = PublicAccountSerializer()
    floor_price = serializers.IntegerField(source="floor")
    volume_traded = serializers.IntegerField(source="volume")

    class Meta:
        model = models.Erc721Collection
        fields = [
            "address",
            "name",
            "symbol",
            "contract_type",
            "external_link",
            "description",
            "slug",
            "image_url",
            "banner_image_url",
            "royalty_per_mille",
            "payout_address",
            "verified",
            "owner",
            "floor_price",
            "volume_traded",
        ]

    def get_image_url(self, instance):
        if instance.profile_image:
            return instance.profile_image.url
        else:
            return instance.profile_image_url


class PublicCollectionSerializerShort(serializers.ModelSerializer):
    external_link = serializers.URLField(source="site_link")
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = models.Erc721Collection
        fields = [
            "address",
            "name",
            "symbol",
            "contract_type",
            "external_link",
            "slug",
            "image_url",
            "verified",
        ]

    def get_image_url(self, instance):
        if instance.profile_image:
            return instance.profile_image.url
        else:
            return instance.profile_image_url


class PublicTokenSerializer(serializers.ModelSerializer):
    image_url = serializers.URLField(source="image")
    collection = PublicCollectionSerializerShort()
    owner = PublicAccountSerializer()
    traits = serializers.ListField(source="attributes")

    class Meta:
        model = models.Erc721Token
        fields = [
            "token_id",
            "name",
            "external_url",
            "description",
            "image_url",
            "animation_url",
            "background_color",
            "collection",
            "owner",
            "traits",
        ]


class PublicTokenSerializerShort(serializers.ModelSerializer):
    image_url = serializers.URLField(source="image")
    collection = PublicCollectionSerializerShort()
    owner = PublicAccountSerializer()

    class Meta:
        model = models.Erc721Token
        fields = [
            "token_id",
            "name",
            "external_url",
            "description",
            "image_url",
            "animation_url",
            "background_color",
            "collection",
            "owner",
        ]


class PublicTokenSerializerForAccount(serializers.ModelSerializer):
    image_url = serializers.URLField(source="image")
    collection = PublicCollectionSerializerShort()

    class Meta:
        model = models.Erc721Token
        fields = [
            "token_id",
            "name",
            "external_url",
            "description",
            "image_url",
            "animation_url",
            "background_color",
            "collection",
        ]


class PublicActivitySerializer(serializers.ModelSerializer):
    from_profile = PublicAccountSerializer()
    to_profile = PublicAccountSerializer()
    token = PublicTokenSerializerShort()

    order_type = serializers.SerializerMethodField()
    order_status = serializers.SerializerMethodField()
    start_price = serializers.SerializerMethodField()
    end_price = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    start_time = serializers.SerializerMethodField()
    end_time = serializers.SerializerMethodField()
    quantity = serializers.SerializerMethodField()

    class Meta:
        model = models.Erc721Activity
        fields = [
            "event_type",
            "order_type",
            "order_status",
            "timestamp",
            "txn_id",
            "from_profile",
            "to_profile",
            "start_price",
            "end_price",
            "currency",
            "start_time",
            "end_time",
            "quantity",
            "token",
        ]

    def get_order_type(self, instance):
        if instance.sell_order:
            return "fixed_price"
        elif instance.buy_order:
            return "offer"
        elif instance.dutch_auction:
            return "dutch_auction"
        else:
            return None

    def get_order_status(self, instance):
        if instance.sell_order:
            if instance.sell_order.fulfilled:
                return "fulfilled"
            elif instance.sell_order.cancelled:
                return "cancelled"
            elif instance.sell_order.active:
                return "active"
            else:
                return "inactive"
        elif instance.buy_order:
            if instance.buy_order.fulfilled:
                return "fulfilled"
            elif instance.buy_order.cancelled:
                return "cancelled"
            elif instance.buy_order.active:
                return "active"
            else:
                return "inactive"
        elif instance.dutch_auction:
            if instance.dutch_auction.fulfilled:
                return "fulfilled"
            elif instance.dutch_auction.cancelled:
                return "cancelled"
            elif instance.dutch_auction.active:
                return "active"
            else:
                return "inactive"
        else:
            return None

    def get_start_price(self, instance):
        if instance.sell_order:
            return instance.sell_order.price
        elif instance.buy_order:
            return instance.buy_order.price
        elif instance.dutch_auction:
            return instance.dutch_auction.start_price
        else:
            return None

    def get_end_price(self, instance):
        if instance.sell_order:
            return instance.sell_order.price
        elif instance.buy_order:
            return instance.buy_order.price
        elif instance.dutch_auction:
            return instance.dutch_auction.end_price
        else:
            return None

    def get_currency(self, instance):
        if instance.sell_order:
            return instance.sell_order.payment_token.symbol
        elif instance.buy_order:
            return instance.buy_order.payment_token.symbol
        elif instance.dutch_auction:
            return instance.dutch_auction.payment_token.symbol
        else:
            return None

    def get_start_time(self, instance):
        if instance.sell_order:
            return instance.sell_order.start_time
        elif instance.buy_order:
            return instance.buy_order.start_time
        elif instance.dutch_auction:
            return instance.dutch_auction.start_time
        else:
            return None

    def get_end_time(self, instance):
        if instance.sell_order:
            return instance.sell_order.expiration
        elif instance.buy_order:
            return instance.buy_order.expiration
        elif instance.dutch_auction:
            return instance.dutch_auction.end_time
        else:
            return None

    def get_quantity(self, instance):
        if instance.sell_order:
            return instance.sell_order.quantity
        elif instance.buy_order:
            return instance.buy_order.quantity
        elif instance.dutch_auction:
            return instance.dutch_auction.quantity
        else:
            return None
