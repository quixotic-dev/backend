import os

from api import models
from api.utils.filters import (
    collection_activity_filters,
    collection_token_filters,
    explore_token_filters,
)
from api.utils.search_utils import search_collection_tokens
from batch_processing.tasks.token.tasks import refresh_token as queue_refresh_token
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework import mixins, routers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from web3 import Web3
from api.throttles.RabbitHoleThrottle import RabbitHoleThrottle
from . import serializers


class CollectionViewset(
    viewsets.GenericViewSet, mixins.RetrieveModelMixin, mixins.ListModelMixin
):
    queryset = models.Erc721Collection.objects.filter(approved=True)
    serializer_class = serializers.PublicCollectionSerializer
    lookup_field = "address"

    @method_decorator(cache_page(60))  # 1 minute
    def list(self, request, *args, **kwargs):
        collections = self.queryset.filter(delisted=False).order_by("-volume")
        collections = self.paginate_queryset(collections)
        serializer = serializers.PublicCollectionSerializerMedium(
            collections, many=True, context={"request": request}
        )
        return self.get_paginated_response(serializer.data)

    @method_decorator(cache_page(60))  # 1 minute
    def retrieve(self, request, address, *args, **kwargs):
        try:
            collection = models.Erc721Collection.objects.get(
                slug=address, approved=True
            )
        except models.Erc721Collection.DoesNotExist:
            if address.startswith("0x"):
                address = Web3.toChecksumAddress(address)
                collection = get_object_or_404(
                    self.queryset, address=address, approved=True
                )
            else:
                return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = self.serializer_class(collection, context={"request": request})
        return Response(serializer.data)

    @method_decorator(cache_page(60))  # 1 minute
    @action(detail=True, url_path="assets", methods=["GET"])
    def assets(self, request, address, *args, **kwargs):
        try:
            collection = models.Erc721Collection.objects.get(
                slug=address, approved=True
            )
        except models.Erc721Collection.DoesNotExist:
            if address.startswith("0x"):
                address = Web3.toChecksumAddress(address)
                collection = get_object_or_404(
                    self.queryset, address=address, approved=True
                )
            else:
                return Response(status=status.HTTP_404_NOT_FOUND)

        attributes = request.query_params.getlist("attribute")
        sort_tags = request.query_params.getlist("sort")
        chains = request.query_params.getlist("chain")
        availability = request.query_params.get("availability")
        price = request.query_params.get("price")
        payment_token = request.query_params.get("currency")
        search_query = request.query_params.get("query")

        if availability == "all":
            availability = False

        if payment_token == "all":
            payment_token = False

        if search_query:
            tokens = search_collection_tokens(search_query, collection)

        elif (
            attributes or sort_tags or availability or price or payment_token or chains
        ):
            try:
                tokens = collection_token_filters(
                    attributes,
                    sort_tags,
                    availability,
                    price,
                    payment_token,
                    chains,
                    collection.id,
                )
            except Exception as e:
                print(e)
                return Response(status=status.HTTP_400_BAD_REQUEST)
        else:
            tokens = collection.erc721token_set.filter(approved=True).order_by(
                "-for_sale", "price", "id"
            )

        page = self.paginate_queryset(tokens)
        serializer = serializers.PublicTokenSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @method_decorator(cache_page(60))  # 1 minute
    @action(detail=True, url_path="activity", methods=["GET"])
    def activity(self, request, address, *args, **kwargs):
        try:
            collection = models.Erc721Collection.objects.get(
                slug=address, approved=True
            )
        except models.Erc721Collection.DoesNotExist:
            if address.startswith("0x"):
                address = Web3.toChecksumAddress(address)
                collection = get_object_or_404(
                    models.Erc721Collection, address=address, approved=True
                )
            else:
                return Response(status=status.HTTP_404_NOT_FOUND)

        events = request.query_params.getlist("event")
        sort_tags = request.query_params.getlist("activity_sort")
        chains = request.query_params.getlist("chain")
        attributes = request.query_params.getlist("attribute")
        price = request.query_params.get("price")
        payment_token = request.query_params.get("currency")

        if payment_token == "all":
            payment_token = False

        if events or sort_tags or attributes or price or payment_token or chains:
            try:
                activities = collection_activity_filters(
                    events,
                    sort_tags,
                    attributes,
                    price,
                    payment_token,
                    chains,
                    collection.id,
                )
            except Exception as e:
                print(e)
                return Response(status=status.HTTP_400_BAD_REQUEST)
        else:
            activities = collection.activity()

        page = self.paginate_queryset(activities)
        serializer = serializers.PublicActivitySerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @method_decorator(cache_page(60))  # 1 minute
    @action(detail=True, url_path="stats", methods=["GET"])
    def stats(self, request, address, *args, **kwargs):
        try:
            collection = models.Erc721Collection.objects.get(
                slug=address, approved=True
            )
        except models.Erc721Collection.DoesNotExist:
            if address.startswith("0x"):
                address = Web3.toChecksumAddress(address)
                collection = get_object_or_404(
                    self.queryset, address=address, approved=True
                )
            else:
                return Response(status=status.HTTP_404_NOT_FOUND)

        one_day_volume = collection.volume_24h
        one_day_sales = collection.sales_24h
        one_day_average_price = (
            (one_day_volume / one_day_sales) if one_day_sales > 0 else 0
        )

        seven_day_volume = collection.volume_7d
        seven_day_sales = collection.sales_7d
        seven_day_average_price = (
            (seven_day_volume / seven_day_sales) if seven_day_sales > 0 else 0
        )

        thirty_day_volume = collection.volume_30d
        thirty_day_sales = collection.sales_30d
        thirty_day_average_price = (
            (thirty_day_volume / thirty_day_sales) if thirty_day_sales > 0 else 0
        )

        average_price = (
            (collection.volume / collection.sales) if collection.sales > 0 else 0
        )

        floor_price = collection.floor / 1000000000 if collection.floor else None

        stats = {
            "stats": {
                "one_day_volume": one_day_volume / 1000000000,
                "one_day_change": collection.volume_change_24h(),
                "one_day_sales": one_day_sales,
                "one_day_average_price": one_day_average_price / 1000000000,
                "seven_day_volume": seven_day_volume / 1000000000,
                "seven_day_change": collection.volume_change_7d(),
                "seven_day_sales": seven_day_sales,
                "seven_day_average_price": seven_day_average_price / 1000000000,
                "thirty_day_volume": thirty_day_volume / 1000000000,
                "thirty_day_change": collection.volume_change_30d(),
                "thirty_day_sales": thirty_day_sales,
                "thirty_day_average_price": thirty_day_average_price / 1000000000,
                "total_volume": collection.volume / 1000000000,
                "total_listed": collection.listed,
                "total_sales": collection.sales,
                "total_supply": collection.supply,
                "count": collection.supply,
                "num_owners": collection.owners,
                "average_price": average_price / 1000000000,
                "floor_price": floor_price,
            }
        }
        return Response(data=stats, status=200)

    @method_decorator(cache_page(60 * 10))  # 10 minutes
    @action(detail=True, url_path="daily-stats", methods=["GET"])
    def daily_stats(self, request, address, *args, **kwargs):
        try:
            collection = models.Erc721Collection.objects.get(
                slug=address, approved=True
            )
        except models.Erc721Collection.DoesNotExist:
            if address.startswith("0x"):
                address = Web3.toChecksumAddress(address)
                collection = get_object_or_404(
                    self.queryset, address=address, approved=True
                )
            else:
                return Response(status=status.HTTP_404_NOT_FOUND)

        print(collection)
        daily_stats = collection.daily_stats()
        print(daily_stats)
        return Response(data=daily_stats, status=200)


class AssetViewset(viewsets.ModelViewSet):
    queryset = models.Erc721Token.objects.filter(approved=True)
    serializer_class = serializers.PublicTokenSerializer

    @method_decorator(cache_page(60))  # 1 minute
    def list(self, request, *args, **kwargs):
        collections = request.query_params.getlist("collection")
        sort_tags = request.query_params.getlist("sort")
        availability = request.query_params.get("availability")
        price = request.query_params.get("price")
        payment_token = request.query_params.get("currency")

        if availability == "all":
            availability = False

        if payment_token == "all":
            payment_token = False

        if collections or sort_tags or availability or price or payment_token:
            try:
                tokens = explore_token_filters(
                    collections, sort_tags, availability, price, payment_token
                )
            except Exception as e:
                print(e)
                return Response(status=status.HTTP_400_BAD_REQUEST)
        else:
            tokens = self.queryset

        page = self.paginate_queryset(tokens)
        serializer = serializers.PublicTokenSerializerShort(page, many=True)
        return self.get_paginated_response(serializer.data)

    @method_decorator(cache_page(60))  # 1 minute
    def retrieve(self, request, pk, *args, **kwargs):
        address, token_id = pk.split(":")
        try:
            int(token_id)
        except Exception:
            return Response(status=status.HTTP_404_NOT_FOUND)

        try:
            address = Web3.toChecksumAddress(address)
        except Exception:
            return Response(status=status.HTTP_404_NOT_FOUND)
        collection = get_object_or_404(
            models.Erc721Collection.objects.all(), address=address, approved=True
        )
        token = get_object_or_404(
            self.queryset, collection=collection, token_id=token_id
        )
        serializer = self.serializer_class(token)
        return Response(serializer.data)

    # @action(detail=True, url_path="refresh-metadata", methods=["PUT"])
    # def refresh_metadata(self, request, pk, *arg, **kwargs):
    #     address, token_id = pk.split(":")
    #     try:
    #         address = Web3.toChecksumAddress(address)
    #     except Exception:
    #         return Response(status=status.HTTP_404_NOT_FOUND)
    #     collection = get_object_or_404(
    #         models.Erc721Collection.objects.all(), address=address, approved=True
    #     )
    #     token = get_object_or_404(
    #         self.queryset, collection=collection, token_id=token_id
    #     )
    #     if os.environ.get("USE_CELERY_PROCESS_TXN"):
    #         queue_refresh_token.apply_async((token.id,), queue="refresh_token")
    #         return Response(status=202)
    #     else:
    #         token.refresh_token()
    #         return Response(status=200)


class AccountViewset(viewsets.ModelViewSet):
    queryset = models.Profile.objects
    serializer_class = serializers.PublicAccountSerializer

    @method_decorator(cache_page(60))  # 1 minute
    def retrieve(self, request, pk, *args, **kwargs):
        try:
            address = Web3.toChecksumAddress(pk)
            profile = get_object_or_404(self.queryset, address=address)
        except Exception as e:
            print(e)
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = self.serializer_class(profile)
        return Response(serializer.data)

    @method_decorator(cache_page(60))  # 1 minute
    @action(detail=True, url_path="assets", methods=["GET"])
    def tokens(self, request, pk, *args, **kwargs):
        try:
            address = Web3.toChecksumAddress(pk)
            profile = get_object_or_404(self.queryset, address=address)
        except Exception as e:
            print(e)
            return Response(status=status.HTTP_404_NOT_FOUND)

        tokens = profile.tokens(pull_erc721s=True, pull_erc1155s=False)
        page = self.paginate_queryset(tokens)
        serializer = serializers.PublicTokenSerializerForAccount(page, many=True)
        return self.get_paginated_response(serializer.data)


class RabbitHoleViewset(viewsets.ModelViewSet):
    queryset = models.Erc721Activity.objects
    serializer_class = serializers.PublicActivitySerializer
    throttle_classes = [RabbitHoleThrottle]

    def list(self, request, *args, **kwargs):
        return Response(status=status.HTTP_404_NOT_FOUND)

    @method_decorator(cache_page(10))  # 10 seconds
    def retrieve(self, request, pk, *args, **kwargs):
        try:
            address = Web3.toChecksumAddress(pk)
            to_profile = get_object_or_404(models.Profile, address=address)
            from_profile = get_object_or_404(
                models.Profile, address="0x0000000000000000000000000000000000000000"
            )

            # Todo: update to RabbitHole contract once deployed
            smart_contract = get_object_or_404(
                models.Contract,
                address="0x74A002D13f5F8AF7f9A971f006B9a46c9b31DaBD",
            )

            activity = get_object_or_404(
                self.queryset,
                from_profile=from_profile,
                to_profile=to_profile,
                token__smart_contract=smart_contract,
            )
        except Exception as e:
            print(e)
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = self.serializer_class(activity)
        return Response(serializer.data)


router = routers.DefaultRouter()
router.register("collection", CollectionViewset)
router.register("collections", CollectionViewset)
router.register("asset", AssetViewset)
router.register("assets", AssetViewset)
router.register("account", AccountViewset)
router.register("rabbithole", RabbitHoleViewset)

router.register("opt/collection", CollectionViewset)
router.register("opt/collections", CollectionViewset)
router.register("opt/asset", AssetViewset)
router.register("opt/assets", AssetViewset)
router.register("opt/account", AccountViewset)
