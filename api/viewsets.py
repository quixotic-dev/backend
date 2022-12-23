import base64
import json
import os
import re
from datetime import datetime, timezone
from random import sample, shuffle

import requests
from django.db.models import F, Q
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework import mixins, routers, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from web3 import Web3

from api.paginators.QuixCollectionPaginator import QuixCollectionPaginator
from api.utils.constants import (
    BRIDGE_PROFILE_INTERNAL_ID,
    NETWORK,
    NULL_PROFILE_INTERNAL_ID,
    L2ERC721_BRIDGE
)
from api.utils.contract_utils import get_or_create_contract
from api.utils.Erc165Contract import Erc165Contract
from api.utils.Erc721Contract import Erc721Contract
from api.utils.ERC721Factory import Erc721Factory
from api.utils.rest_framework.paginator import LightweightPageNumberPagination
from api.utils.restricted_usernames import is_restricted
from batch_processing.tasks.token.tasks import refresh_token as queue_refresh_token
from launchpad.models import HostedCollection

from . import models, serializers
from .model_factory import create_seaport_buy_order, create_seaport_sell_order
from .utils.chain_data import get_balances
from .utils.ens_utils import get_address_for_ens
from .utils.filters import (
    collection_activity_filters,
    collection_token_filters,
    explore_activity_filters,
    explore_token_filters,
    profile_activity_filters,
    profile_token_filters,
)
from .utils.L2Erc721Contract import L2Erc721Contract
from .utils.order_utils import create_timestamps
from .utils.request_utils import UnsafeInputException, check_request_body
from .utils.seaport.orders import (
    validate_seaport_buy_order,
    validate_seaport_sell_order,
)
from .utils.seaport.validate_order import SignatureValidationFailed
from .utils.search_utils import (
    search_collection_tokens,
    search_collections,
    search_profile_tokens,
    search_profiles,
)
from .utils.signature_utils import verify_collection_signature, verify_profile_signature


# TODO: Protect endpoints with JWT auth
class ProfileViewset(viewsets.ModelViewSet):
    queryset = models.Profile.objects.all()
    serializer_class = serializers.ProfileSerializer
    pagination_class = LightweightPageNumberPagination
    lookup_field = "address"

    def create(self, request, *args, **kwargs):
        identifier = request.data.get("address")
        if (
            identifier.endswith(".eth")
            or identifier.endswith(".xyz")
            or identifier.endswith(".id")
        ):
            try:
                address = get_address_for_ens(identifier)
                profile = models.Profile.objects.create(address=address)
            except Exception as e:
                print((str(e)))
                return Response(status=status.HTTP_404_NOT_FOUND)

        elif identifier.startswith("0x"):
            try:
                address = Web3.toChecksumAddress(identifier)
                profile = models.Profile.objects.create(address=address)
            except Exception as e:
                print((str(e)))
                return Response(status=status.HTTP_404_NOT_FOUND)

        else:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = self.serializer_class(profile)
        return Response(serializer.data)

    def retrieve(self, request, address, *args, **kwargs):
        # print(f"We're retrieving a profile: {address}")
        try:
            address = Web3.toChecksumAddress(address)
        except Exception as e:
            print((str(e)))
            return Response(status=status.HTTP_404_NOT_FOUND)

        profile, created = models.Profile.objects.get_or_create(address=address)
        serializer = self.get_serializer(profile)
        return Response(serializer.data)

    @method_decorator(cache_page(60 * 5))  # 5 minutes
    @action(detail=False, url_path="most-followed", methods=["GET"])
    def most_followed(self, request, *args, **kwargs):
        # profiles = sorted(self.queryset, key=lambda c: c.follower_count(), reverse=True)[:10]
        profiles = list(models.Profile.objects.exclude(username__isnull=True))
        shuffle(profiles)
        serializer = serializers.ProfileSerializerForSearch(profiles[:12], many=True)
        return Response(serializer.data)

    @method_decorator(cache_page(60))  # 60 seconds
    @action(detail=False, url_path="get-profile", methods=["GET"])
    def get_profile(self, request):
        identifier = request.query_params.get("address")
        if (
            identifier.endswith(".eth")
            or identifier.endswith(".xyz")
            or identifier.endswith(".id")
        ):
            try:
                profile = models.Profile.objects.get(reverse_ens=identifier)
            except models.Profile.DoesNotExist:
                try:
                    address = get_address_for_ens(identifier)
                    profile = models.Profile.objects.get(address=address)
                except Exception as e:
                    print((str(e)))
                    return Response(status=status.HTTP_404_NOT_FOUND)

        elif identifier.startswith("0x"):
            try:
                address = Web3.toChecksumAddress(identifier)
                profile = models.Profile.objects.get(address=address)
            except Exception as e:
                profile = get_object_or_404(models.Profile, username=identifier)

        else:
            profile = get_object_or_404(models.Profile, username=identifier)

        serializer = self.get_serializer(profile)
        return Response(serializer.data)

    @action(detail=True, url_path="settings", methods=["POST"])
    def profile_settings(self, request, address):
        message = request.data.get("message")
        signature = request.data.get("signature")

        if not message or not signature:
            return Response(data={"error": "message not signed"}, status=400)

        if not verify_profile_signature(message, signature, address):
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            address = Web3.toChecksumAddress(address)
        except Exception as e:
            print((str(e)))
            return Response(status=status.HTTP_404_NOT_FOUND)

        profile, created = models.Profile.objects.get_or_create(address=address)
        serializer = serializers.ProfileSettingsSerializer(profile)
        return Response(serializer.data)

    @action(detail=True, url_path="collection-thresholds", methods=["GET"])
    def collection_thresholds(self, request, address):
        profile = get_object_or_404(models.Profile, address=address)
        collection_thresholds = models.CollectionOfferThreshold.objects.filter(
            profile=profile
        )
        serializer = serializers.CollectionOfferThresholdSerializer(
            collection_thresholds, many=True
        )

        result = {}
        for item in serializer.data:
            result[item["collection"]["address"]] = item["minimum_offer"]
        return Response(result)

    @action(detail=True, url_path="update-collection-thresholds", methods=["POST"])
    def update_collection_thresholds(self, request, address):
        try:
            check_request_body(request)
        except UnsafeInputException:
            return Response(status=400)

        message = request.data.get("message")
        signature = request.data.get("signature")

        if not message or not signature:
            return Response(data={"error": "message not signed"}, status=400)

        if not verify_profile_signature(message, signature, address):
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        profile = get_object_or_404(models.Profile, address=address)
        thresholds = request.data
        for col_address, minimum_offer in thresholds.items():
            try:
                if minimum_offer < 100000:
                    return Response(status=400)
                elif minimum_offer > 500000000000:
                    return Response(status=400)

                collection = models.Erc721Collection.objects.get(address=col_address)
                (
                    offer_threshold,
                    _created,
                ) = models.CollectionOfferThreshold.objects.get_or_create(
                    profile=profile, collection=collection
                )
                offer_threshold.minimum_offer = minimum_offer
                offer_threshold.save()
            except Exception as e:
                print(e)
                continue

        return Response(status=200)

    @action(detail=True, url_path="update-notification-settings", methods=["POST"])
    def update_notification_settings(self, request, address):
        try:
            check_request_body(request)
        except UnsafeInputException:
            return Response(status=400)

        message = request.data.get("message")
        signature = request.data.get("signature")

        if not message or not signature:
            return Response(data={"error": "message not signed"}, status=400)

        if not verify_profile_signature(message, signature, address):
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        profile = get_object_or_404(models.Profile, address=address)
        try:
            profile.email = request.data.get("email")
            profile.minimum_offer = request.data.get("minimum_offer")
            profile.save()
            return Response(status=200)
        except Exception as e:
            print(e)
            return Response(status=500)

    @action(detail=True, url_path="update-profile-settings", methods=["POST"])
    def update_profile_settings(self, request, address):
        try:
            check_request_body(request)
        except UnsafeInputException:
            return Response(status=400)

        message = request.data.get("message")
        signature = request.data.get("signature")

        if not message or not signature:
            return Response(data={"error": "message not signed"}, status=400)

        if not verify_profile_signature(message, signature, address):
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        profile = get_object_or_404(models.Profile, address=address)
        try:
            if request.data.get("username"):
                profile.username = re.sub("[\W]+", "", request.data.get("username"))[
                    :15
                ].lower()
                if is_restricted(profile.username):
                    return Response(data={"error": "username unavailable"}, status=400)
            else:
                profile.username = None

            profile.bio = request.data.get("bio")
            profile.twitter = request.data.get("twitter")

            img = request.data.get("img")
            if img:
                profile.profile_image = img
            elif request.data.get("shouldDeleteImage") == "true":
                profile.profile_image = None

            cover_image = request.data.get("cover_image")
            if cover_image:
                profile.cover_image = cover_image
            elif request.data.get("shouldDeleteCoverImage") == "true":
                profile.cover_image = None

            profile.save()
            return Response(status=200)
        except Exception as e:
            print(e)
            if str(e).startswith("UNIQUE constraint failed") or str(e).startswith(
                "duplicate key value violates unique constraint"
            ):
                return Response(data={"error": "username already taken"}, status=400)
            else:
                return Response(status=500)

    @action(detail=False, url_path="get-ens", methods=["GET"])
    def get_ens(self, request):
        ens = request.query_params.get("ens")
        if not ens:
            return Response(status=status.HTTP_404_NOT_FOUND)
        address = get_address_for_ens(ens)
        return Response(data={"address": address}, status=200)

    @method_decorator(cache_page(10))  # 10 seconds
    @action(
        detail=True,
        url_path="tokens",
        methods=["GET"],
        pagination_class=PageNumberPagination,
    )
    def tokens(self, request, address):
        address = Web3.toChecksumAddress(address)
        profile = get_object_or_404(models.Profile, address=address)

        collections = request.query_params.getlist("collection", [])
        sort_tags = request.query_params.getlist("sort", ["price:desc"])
        availability = request.query_params.get("availability", "all")
        price = request.query_params.get("price", None)
        payment_token = request.query_params.get("currency", "all")
        chains = request.query_params.getlist("chain", [])
        search_query = request.query_params.get("query", "")

        if availability == "all":
            availability = False

        if payment_token == "all":
            payment_token = False

        has_any_1155_tokens = models.Erc1155TokenOwner.objects.filter(
            owner=profile
        ).exists()

        if search_query:
            tokens = search_profile_tokens(search_query, profile)
        elif (
            len(collections) == 0
            and sort_tags == ["price:desc"]
            and availability is False
            and price is None
            and payment_token is False
        ):
            print("Following default path: tokens")
            tokens = profile.tokens(pull_erc1155s=has_any_1155_tokens)
            tokens = (
                tokens.prefetch_related("collection")
                .select_related("last_sale_payment_token")
                .select_related("highest_offer_payment_token")
            )
        else:
            try:
                tokens = profile_token_filters(
                    collections,
                    sort_tags,
                    availability,
                    price,
                    payment_token,
                    chains,
                    profile.id,
                    pull_erc1155s=has_any_1155_tokens,
                )
            except Exception as e:
                print(e)
                return Response(status=status.HTTP_400_BAD_REQUEST)

        page = self.paginate_queryset(tokens)
        serializer = serializers.TokenSerializerForProfile(
            page, many=True, context={"owner_ctx": profile.address}
        )
        return self.get_paginated_response(serializer.data)

    @method_decorator(cache_page(10))  # 10 seconds
    @action(
        detail=True,
        url_path="erc721tokens",
        methods=["GET"],
        pagination_class=PageNumberPagination,
    )
    def erc721tokens(self, request, address):
        address = Web3.toChecksumAddress(address)
        profile = get_object_or_404(models.Profile, address=address)

        collections = request.query_params.getlist("collection", [])
        sort_tags = request.query_params.getlist("sort", ["price:desc"])
        availability = request.query_params.get("availability", "all")
        price = request.query_params.get("price", None)
        payment_token = request.query_params.get("currency", "all")
        chains = request.query_params.getlist("chain", [])
        search_query = request.query_params.get("query", "")

        if availability == "all":
            availability = False

        if payment_token == "all":
            payment_token = False

        if search_query:
            tokens = search_profile_tokens(search_query, profile)
        elif (
            len(collections) == 0
            and sort_tags == ["price:desc"]
            and availability is False
            and price is None
            and payment_token is False
        ):
            tokens = profile.tokens(pull_erc721s=True, pull_erc1155s=False)
            tokens = (
                tokens.prefetch_related("collection")
                .select_related("last_sale_payment_token")
                .select_related("highest_offer_payment_token")
            )
        else:
            try:
                tokens = profile_token_filters(
                    collections,
                    sort_tags,
                    availability,
                    price,
                    payment_token,
                    chains,
                    profile.id,
                    pull_erc721s=True,
                    pull_erc1155s=False,
                )
            except Exception as e:
                print(e)
                return Response(status=status.HTTP_400_BAD_REQUEST)

        page = self.paginate_queryset(tokens)
        serializer = serializers.TokenSerializerForProfile(
            page, many=True, context={"owner_ctx": profile.address}
        )
        return self.get_paginated_response(serializer.data)

    @method_decorator(cache_page(10))  # 10 seconds
    @action(
        detail=True,
        url_path="erc1155tokens",
        methods=["GET"],
        pagination_class=PageNumberPagination,
    )
    def erc1155tokens(self, request, address):
        address = Web3.toChecksumAddress(address)
        profile = get_object_or_404(models.Profile, address=address)

        collections = request.query_params.getlist("collection", [])
        sort_tags = request.query_params.getlist("sort", ["price:desc"])
        availability = request.query_params.get("availability", "all")
        price = request.query_params.get("price", None)
        payment_token = request.query_params.get("currency", "all")
        chains = request.query_params.getlist("chain", [])
        search_query = request.query_params.get("query", "")

        has_any_1155_tokens = models.Erc1155TokenOwner.objects.filter(
            owner=profile
        ).exists()
        if not has_any_1155_tokens:
            tokens = models.Erc721Token.objects.none()
            page = self.paginate_queryset(tokens)
            serializer = serializers.TokenSerializerForProfile(
                page, many=True, context={"owner_ctx": profile.address}
            )
            return self.get_paginated_response(serializer.data)

        if availability == "all":
            availability = False

        if payment_token == "all":
            payment_token = False

        if search_query:
            tokens = search_profile_tokens(search_query, profile)
        elif (
            len(collections) == 0
            and sort_tags == ["price:desc"]
            and availability is False
            and price is None
            and payment_token is False
        ):
            tokens = profile.tokens(pull_erc721s=False, pull_erc1155s=True)
            tokens = (
                tokens.prefetch_related("collection")
                .select_related("last_sale_payment_token")
                .select_related("highest_offer_payment_token")
            )
        else:
            try:
                tokens = profile_token_filters(
                    collections,
                    sort_tags,
                    availability,
                    price,
                    payment_token,
                    chains,
                    profile.id,
                    pull_erc721s=False,
                    pull_erc1155s=True,
                )
            except Exception as e:
                print(e)
                return Response(status=status.HTTP_400_BAD_REQUEST)

        page = self.paginate_queryset(tokens)
        serializer = serializers.TokenSerializerForProfile(
            page, many=True, context={"owner_ctx": profile.address}
        )
        return self.get_paginated_response(serializer.data)

    @action(detail=True, url_path="hidden-tokens", methods=["GET"])
    def hidden_tokens(self, request, address):
        address = Web3.toChecksumAddress(address)
        profile = get_object_or_404(models.Profile, address=address)
        page = self.paginate_queryset(profile.hidden_tokens())
        serializer = serializers.TokenSerializerMedium(page, many=True)
        return self.get_paginated_response(serializer.data)

    @method_decorator(cache_page(60))  # Cache profile activity for 1 minute
    @action(detail=True, url_path="activity", methods=["GET"])
    def activity(self, request, address):
        address = Web3.toChecksumAddress(address)
        profile = get_object_or_404(models.Profile, address=address)

        collections = request.query_params.getlist("collection")
        sort_tags = request.query_params.getlist("activity_sort")
        events = request.query_params.getlist("event")
        price = request.query_params.get("price")
        payment_token = request.query_params.get("currency")
        chains = request.query_params.getlist("chain")

        if payment_token == "all":
            payment_token = False

        if collections or sort_tags or events or price or payment_token:
            try:
                activities = profile_activity_filters(
                    collections,
                    sort_tags,
                    events,
                    price,
                    payment_token,
                    chains,
                    profile.id,
                )
            except Exception as e:
                print(e)
                return Response(status=status.HTTP_400_BAD_REQUEST)
        else:
            activities = profile.activity()

        page = self.paginate_queryset(activities)
        serializer = serializers.OnChainActivitySerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, url_path="listed-tokens", methods=["GET"])
    def listed_tokens(self, request, address):
        address = Web3.toChecksumAddress(address)
        profile = get_object_or_404(models.Profile, address=address)

        tokens = (
            profile.sell_orders.filter(
                active=True,
                fulfilled=False,
                cancelled=False,
                expiration__gt=datetime.now(timezone.utc),
            )
            .values_list("token", flat=True)
            .distinct()
        )
        tokens = models.Erc721Token.objects.filter(
            Q(owner=profile) | Q(erc1155tokenowner__owner=profile), id__in=tokens
        ).order_by("-price_eth", "-collection", "-id")

        page = self.paginate_queryset(tokens)
        serializer = serializers.TokenSerializerMedium(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, url_path="unlisted-tokens", methods=["GET"])
    def unlisted_tokens(self, request, address):
        address = Web3.toChecksumAddress(address)
        profile = get_object_or_404(models.Profile, address=address)

        listed_tokens = (
            profile.sell_orders.filter(
                fulfilled=False,
                cancelled=False,
                expiration__gt=datetime.now(timezone.utc),
            )
            .values_list("token", flat=True)
            .distinct()
        )

        tokens = (
            models.Erc721Token.objects.filter(
                Q(owner=profile) | Q(erc1155tokenowner__owner=profile),
                approved=True,
                collection__approved=True,
                collection__non_transferable=False,
                smart_contract__network__network_id=NETWORK,
            )
            .exclude(id__in=listed_tokens)
            .order_by("-collection", "-id")
        )

        page = self.paginate_queryset(tokens)
        serializer = serializers.TokenSerializerMedium(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, url_path="offers-made", methods=["GET"])
    def offers_made(self, request, address):
        address = Web3.toChecksumAddress(address)
        profile = get_object_or_404(models.Profile, address=address)

        offers = profile.buy_orders.filter(
            fulfilled=False, cancelled=False, expiration__gt=datetime.now(timezone.utc)
        )

        page = self.paginate_queryset(offers)
        serializer = serializers.BuyOrderSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, url_path="offers-received", methods=["GET"])
    def offers_received(self, request, address):
        address = Web3.toChecksumAddress(address)
        profile = get_object_or_404(models.Profile, address=address)

        offers = models.Erc721BuyOrder.objects.filter(
            active=True,
            token__smart_contract__type=models.CollectionType.ERC721,
            token__in=profile.all_tokens(),
        )

        page = self.paginate_queryset(offers)
        serializer = serializers.BuyOrderSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @method_decorator(cache_page(30))  # 30 seconds
    @action(detail=True, url_path="followed-profiles", methods=["GET"])
    def followed_profiles(self, request, address):
        address = Web3.toChecksumAddress(address)
        profile = get_object_or_404(models.Profile, address=address)

        profiles = profile.followed_profiles_full()
        page = self.paginate_queryset(profiles)
        serializer = serializers.ProfileSerializerForSearch(page, many=True)
        return self.get_paginated_response(serializer.data)

    @method_decorator(cache_page(30))  # 30 seconds
    @action(detail=True, url_path="followed-collections", methods=["GET"])
    def followed_collections(self, request, address):
        address = Web3.toChecksumAddress(address)
        profile = get_object_or_404(models.Profile, address=address)

        collections = profile.followed_collections_full()
        page = self.paginate_queryset(collections)
        serializer = serializers.CollectionSerializerMedium(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, url_path="follow", methods=["POST"])
    def follow(self, request, address):
        follow_address = request.data.get("follow_address")
        type = request.data.get("type")

        try:
            address = Web3.toChecksumAddress(address)
            follow_address = Web3.toChecksumAddress(follow_address)
        except Exception:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        profile = get_object_or_404(models.Profile, address=address)
        followed_collection = None
        followed_profile = None

        if type == "collection":
            followed_collection = get_object_or_404(
                models.Erc721Collection, address=follow_address
            )
        elif type == "profile":
            followed_profile = get_object_or_404(models.Profile, address=follow_address)
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        profile_follow, _created = models.ProfileFollow.objects.get_or_create(
            profile=profile,
            followed_collection=followed_collection,
            followed_profile=followed_profile,
        )
        serializer = self.get_serializer(profile)
        return Response(serializer.data)

    @action(detail=True, url_path="unfollow", methods=["POST"])
    def unfollow(self, request, address):
        follow_address = request.data.get("follow_address")
        type = request.data.get("type")

        try:
            address = Web3.toChecksumAddress(address)
            follow_address = Web3.toChecksumAddress(follow_address)
        except Exception:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        profile = get_object_or_404(models.Profile, address=address)
        followed_collection = None
        followed_profile = None

        if type == "collection":
            followed_collection = get_object_or_404(
                models.Erc721Collection, address=follow_address
            )
        elif type == "profile":
            followed_profile = get_object_or_404(models.Profile, address=follow_address)
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        try:
            profile_follow = models.ProfileFollow.objects.get(
                profile=profile,
                followed_collection=followed_collection,
                followed_profile=followed_profile,
            )
            profile_follow.delete()
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
        except Exception as e:
            print(e)
            return Response(status=status.HTTP_400_BAD_REQUEST)

    @method_decorator(cache_page(60))  # 1 minute
    @action(detail=True, url_path="notifications", methods=["GET"])
    def notifications(self, request, address):
        address = Web3.toChecksumAddress(address)
        profile = get_object_or_404(models.Profile, address=address)
        notifications = self.paginate_queryset(
            profile.notifications.filter(token__collection__approved=True).order_by(
                "-timestamp"
            )
        )[:4]
        serializer = serializers.NotificationSerializer(notifications, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, url_path="notifications-read", methods=["POST"])
    def notifications_read(self, request, address):
        address = Web3.toChecksumAddress(address)
        profile = get_object_or_404(models.Profile, address=address)
        profile.notifications_read = True
        profile.save()
        return Response(status=200)

    @method_decorator(cache_page(60))  # 1 minute
    @action(detail=True, url_path="notification-status", methods=["GET"])
    def notification_status(self, request, address):
        address = Web3.toChecksumAddress(address)
        profile = get_object_or_404(models.Profile, address=address)
        return Response(
            data={"notifications_read": profile.notifications_read}, status=200
        )

    @action(detail=True, url_path="likes", methods=["GET"])
    def likes(self, request, address):
        address = Web3.toChecksumAddress(address)
        profile = get_object_or_404(models.Profile, address=address)
        likes = self.paginate_queryset(profile.likes())
        serializer = serializers.TokenLikeSerializer(likes, many=True)
        return self.get_paginated_response(serializer.data)

    @method_decorator(cache_page(30))  # 30 seconds
    @action(detail=True, url_path="get-balances", methods=["GET"])
    def get_balances(self, request, address):
        try:
            address = Web3.toChecksumAddress(address)
        except ValueError:
            return Response(status=status.HTTP_404_NOT_FOUND)
        balances = get_balances(address)
        return Response(data=balances)

    @method_decorator(cache_page(15 * 60))  # 1 minute
    @action(detail=True, url_path="collections", methods=["GET"])
    def collections(self, request, address):
        address = Web3.toChecksumAddress(address)
        profile = get_object_or_404(models.Profile, address=address)
        collections = self.paginate_queryset(profile.collections())
        serializer = serializers.CollectionSerializerForSearch(collections, many=True)
        return self.get_paginated_response(serializer.data)

    @method_decorator(cache_page(60))  # 1 minute
    @action(detail=True, url_path="owned-collections", methods=["GET"])
    def owned_collections(self, request, address):
        address = Web3.toChecksumAddress(address)
        profile = get_object_or_404(models.Profile, address=address)
        collections = models.Erc721Collection.objects.filter(
            approved=True, owner=profile
        )
        collections = self.paginate_queryset(collections)
        serializer = serializers.CollectionSerializerMedium(collections, many=True)
        return self.get_paginated_response(serializer.data)

    @method_decorator(cache_page(60))  # 1 minute
    @action(detail=True, url_path="erc721-collections", methods=["GET"])
    def erc721_collections(self, request, address):
        address = Web3.toChecksumAddress(address)
        profile = get_object_or_404(models.Profile, address=address)
        collections = self.paginate_queryset(profile.erc721Collections())
        serializer = serializers.CollectionSerializerForSearch(collections, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, url_path="hide-token", methods=["POST"])
    def hide_token(self, request, address):
        collection_address = request.data.get("collection_address")
        token_id = request.data.get("token_id")

        try:
            address = Web3.toChecksumAddress(address)
            collection_address = Web3.toChecksumAddress(collection_address)
        except Exception:
            return Response(status=status.HTTP_404_NOT_FOUND)

        profile = get_object_or_404(models.Profile, address=address)
        smart_contract = get_object_or_404(
            models.Contract,
            address=collection_address,
            approved=True,
            collection__approved=True,
        )
        token = get_object_or_404(
            models.Erc721Token, smart_contract=smart_contract, token_id=token_id
        )

        hidden_token, _created = models.HiddenToken.objects.get_or_create(
            user=profile, token=token
        )
        return Response(status=status.HTTP_200_OK)

    @action(detail=True, url_path="show-token", methods=["POST"])
    def show_token(self, request, address):
        collection_address = request.data.get("collection_address")
        token_id = request.data.get("token_id")

        try:
            address = Web3.toChecksumAddress(address)
            collection_address = Web3.toChecksumAddress(collection_address)
        except Exception:
            return Response(status=status.HTTP_404_NOT_FOUND)

        profile = get_object_or_404(models.Profile, address=address)
        smart_contract = get_object_or_404(
            models.Contract,
            address=collection_address,
            approved=True,
            collection__approved=True,
        )
        token = get_object_or_404(
            models.Erc721Token, smart_contract=smart_contract, token_id=token_id
        )

        try:
            hidden_token = models.HiddenToken.objects.get(user=profile, token=token)
            hidden_token.delete()
            return Response(status=status.HTTP_200_OK)
        except models.HiddenToken.DoesNotExist:
            return Response(status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, url_path="feature-token", methods=["POST"])
    def feature_token(self, request, address):
        collection_address = request.data.get("collection_address")
        token_id = request.data.get("token_id")

        try:
            address = Web3.toChecksumAddress(address)
            collection_address = Web3.toChecksumAddress(collection_address)
        except Exception:
            return Response(status=status.HTTP_404_NOT_FOUND)

        profile = get_object_or_404(models.Profile, address=address)
        smart_contract = get_object_or_404(
            models.Contract,
            address=collection_address,
            approved=True,
            collection__approved=True,
        )
        token = get_object_or_404(
            models.Erc721Token, smart_contract=smart_contract, token_id=token_id
        )

        featured_token, _created = models.FeaturedToken.objects.get_or_create(
            user=profile, token=token
        )
        return Response(status=status.HTTP_200_OK)

    @action(detail=True, url_path="unfeature-token", methods=["POST"])
    def unfeature_token(self, request, address):
        collection_address = request.data.get("collection_address")
        token_id = request.data.get("token_id")

        try:
            address = Web3.toChecksumAddress(address)
            collection_address = Web3.toChecksumAddress(collection_address)
        except Exception:
            return Response(status=status.HTTP_404_NOT_FOUND)

        profile = get_object_or_404(models.Profile, address=address)
        smart_contract = get_object_or_404(
            models.Contract,
            address=collection_address,
            approved=True,
            collection__approved=True,
        )
        token = get_object_or_404(
            models.Erc721Token, smart_contract=smart_contract, token_id=token_id
        )

        try:
            featured_token = models.FeaturedToken.objects.get(user=profile, token=token)
            featured_token.delete()
            return Response(status=status.HTTP_200_OK)
        except models.FeaturedToken.DoesNotExist:
            return Response(status=status.HTTP_400_BAD_REQUEST)


class TokenViewset(viewsets.ModelViewSet):
    queryset = models.Erc721Token.objects.filter(approved=True).order_by(
        "-for_sale", "price", "id"
    )
    serializer_class = serializers.TokenSerializer

    @method_decorator(cache_page(5))  # 5 seconds
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
            tokens = models.Erc721Token.objects.filter(
                approved=True, collection__approved=True, collection__is_spam=False
            ).order_by("-for_sale", "price", "id")

        page = self.paginate_queryset(tokens)
        serializer = serializers.TokenSerializerMedium(page, many=True)
        return self.get_paginated_response(serializer.data)

    def retrieve(self, request, pk, *args, **kwargs):
        try:
            address, token_id = pk.split(":")
            network = request.query_params.get("network")
            token_id = str(int(token_id))
        except Exception as e:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if token_id != "0":
            token_id = token_id.lstrip("0")

        if network:
            smart_contract = get_object_or_404(
                models.Contract,
                address=address,
                network__network_id=network,
                approved=True,
                collection__approved=True,
            )
        else:
            smart_contract = get_or_create_contract(address=address, approved_only=True)

        if not smart_contract:
            return Response(status=status.HTTP_404_NOT_FOUND)

        try:
            token = models.Erc721Token.objects.get(
                smart_contract=smart_contract, token_id=token_id
            )
            if token.approved:
                serializer = serializers.TokenSerializer(token)
                return Response(serializer.data)
            else:
                return Response(status=status.HTTP_404_NOT_FOUND)
        except models.Erc721Token.DoesNotExist:
            if smart_contract.token_exists(token_id):
                if smart_contract.type == models.CollectionType.ERC721:
                    token = smart_contract.pull_erc721_token(token_id, queue=False)
                elif smart_contract.type == models.CollectionType.ERC1155:
                    token = smart_contract.pull_erc1155_token(token_id, queue=False)
                serializer = serializers.TokenSerializer(token)
                return Response(serializer.data)
            else:
                return Response(status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, url_path="refresh-token", methods=["PUT"])
    def refresh(self, request, pk, *arg, **kwargs):
        address, token_id = pk.split(":")
        smart_contract = get_object_or_404(
            models.Contract, address=address, approved=True, collection__approved=True
        )
        token = get_object_or_404(
            self.queryset, smart_contract=smart_contract, token_id=token_id
        )
        token.refresh_token()

        if token:
            serializer = serializers.TokenSerializer(token)
            return Response(serializer.data)
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, url_path="queue-refresh", methods=["PUT"])
    def queue_refresh(self, request, pk, *arg, **kwargs):
        address, token_id = pk.split(":")
        smart_contract = get_object_or_404(
            models.Contract, address=address, approved=True, collection__approved=True
        )
        token = get_object_or_404(
            self.queryset, smart_contract=smart_contract, token_id=token_id
        )

        if os.environ.get("USE_CELERY_PROCESS_TXN"):
            queue_refresh_token.apply_async((token.id,), queue="refresh_token")
            return Response(status=202)
        else:
            token.refresh_token()
            return Response(status=200)

    @action(detail=True, url_path="refresh-orders", methods=["PUT"])
    def refresh_orders(self, request, pk, *arg, **kwargs):
        address, token_id = pk.split(":")
        smart_contract = get_object_or_404(
            models.Contract, address=address, approved=True, collection__approved=True
        )
        token = get_object_or_404(
            self.queryset, smart_contract=smart_contract, token_id=token_id
        )
        token.refresh_orders()
        serializer = serializers.TokenSerializer(token)
        return Response(serializer.data)

    @action(detail=True, url_path="refresh-metadata", methods=["PUT"])
    def refresh_metadata(self, request, pk, *arg, **kwargs):
        address, token_id = pk.split(":")
        smart_contract = get_object_or_404(
            models.Contract, address=address, approved=True, collection__approved=True
        )
        token = get_object_or_404(
            self.queryset, smart_contract=smart_contract, token_id=token_id
        )
        token.refresh_metadata()
        serializer = serializers.TokenSerializer(token)
        return Response(serializer.data)

    @action(detail=True, url_path="activity", methods=["GET"])
    def activity(self, request, pk, *args, **kwargs):
        address, token_id = pk.split(":")
        smart_contract = get_object_or_404(
            models.Contract, address=address, approved=True, collection__approved=True
        )
        token = get_object_or_404(
            self.queryset, smart_contract=smart_contract, token_id=token_id
        )
        activities = token.activity()
        page = self.paginate_queryset(activities)
        serializer = serializers.OnChainActivitySerializerShort(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, url_path="owners", methods=["GET"])
    def owners(self, request, pk, *arg, **kwargs):
        profile_address = request.query_params.get("address")
        address, token_id = pk.split(":")
        smart_contract = get_object_or_404(
            models.Contract, address=address, approved=True, collection__approved=True
        )
        token = get_object_or_404(
            self.queryset, smart_contract=smart_contract, token_id=token_id
        )

        if profile_address:
            profile = get_object_or_404(models.Profile, address=profile_address)
            sell_order_count = models.Erc721SellOrder.objects.filter(
                token=token, seller=profile, active=True
            ).count()
            token_owner = get_object_or_404(
                models.Erc1155TokenOwner, token=token, owner=profile
            )
            return Response(
                data={"quantity": token_owner.quantity, "listed": sell_order_count},
                status=200,
            )
        else:
            owners = token.owners()
            page = self.paginate_queryset(owners)
            serializer = serializers.Erc1155TokenOwnerSerializerShort(page, many=True)
            return self.get_paginated_response(serializer.data)

    # TODO: move to profile viewset
    @action(detail=True, url_path="like-token", methods=["POST"])
    def like_token(self, request, pk, *arg, **kwargs):
        profile_address = request.data.get("profile_address")
        address, token_id = pk.split(":")
        smart_contract = get_object_or_404(
            models.Contract, address=address, approved=True, collection__approved=True
        )
        token = get_object_or_404(
            self.queryset, smart_contract=smart_contract, token_id=token_id
        )
        profile = get_object_or_404(models.Profile, address=profile_address)
        token_like, _created = models.TokenLike.objects.get_or_create(
            profile=profile, token=token
        )
        serializer = serializers.ProfileSerializer(profile)
        return Response(serializer.data)

    # TODO: move to profile viewset
    @action(detail=True, url_path="unlike-token", methods=["POST"])
    def unlike_token(self, request, pk, *arg, **kwargs):
        profile_address = request.data.get("profile_address")
        address, token_id = pk.split(":")
        smart_contract = get_object_or_404(
            models.Contract, address=address, approved=True, collection__approved=True
        )
        token = get_object_or_404(
            self.queryset, smart_contract=smart_contract, token_id=token_id
        )
        profile = get_object_or_404(models.Profile, address=profile_address)
        try:
            token_like = models.TokenLike.objects.get(profile=profile, token=token)
            token_like.delete()
            serializer = serializers.ProfileSerializer(profile)
            return Response(serializer.data)
        except models.TokenLike.DoesNotExist:
            return Response(status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, url_path="more-from-collection", methods=["GET"])
    def more_from_collection(self, request, pk, *args, **kwargs):
        address, token_id = pk.split(":")
        collection = get_object_or_404(
            models.Erc721Collection, address=address, approved=True
        )
        token_ids = (
            collection.erc721token_set.filter(approved=True, for_sale=True)
            .exclude(token_id=token_id)
            .values_list("id", flat=True)
        )
        random_token_ids = sample(list(token_ids), min(len(token_ids), 4))
        tokens = collection.erc721token_set.filter(
            approved=True, id__in=random_token_ids
        )
        serializer = serializers.TokenSerializerMedium(tokens, many=True)
        return Response(serializer.data)


class Erc721ActivityViewset(
    viewsets.GenericViewSet, mixins.RetrieveModelMixin, mixins.CreateModelMixin
):
    queryset = models.Erc721Activity.objects.all().order_by("-timestamp")
    serializer_class = serializers.OnChainActivitySerializer

    @method_decorator(cache_page(30))  # 30 seconds
    def list(self, request, *args, **kwargs):
        collections = request.query_params.getlist("collection")
        sort_tags = request.query_params.getlist("activity_sort")
        events = request.query_params.getlist("event")
        price = request.query_params.get("price")
        payment_token = request.query_params.get("currency")

        if payment_token == "all":
            payment_token = False

        if collections or sort_tags or events or price or payment_token:
            try:
                activity = explore_activity_filters(
                    collections, sort_tags, events, price, payment_token
                )
            except Exception as e:
                print(e)
                return Response(status=status.HTTP_400_BAD_REQUEST)
        else:
            on_chain_activity = models.Erc721Activity.objects.filter(
                token__approved=True,
                token__collection__approved=True,
            )
            off_chain_activity = models.OffChainActivity.objects.filter(
                token__approved=True,
                token__collection__approved=True,
            )
            activity = on_chain_activity.union(off_chain_activity).order_by(
                "-timestamp"
            )

        page = self.paginate_queryset(activity)
        serializer = self.serializer_class(page, many=True)
        return self.get_paginated_response(serializer.data)

    def retrieve(self, request, pk, *args, **kwargs):
        activity = models.Erc721Activity.objects.filter(txn_id=pk).first()
        if activity:
            serializer = self.serializer_class(activity)
            return Response(serializer.data)
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)


class Erc721SellOrderViewset(
    viewsets.GenericViewSet, mixins.RetrieveModelMixin, mixins.CreateModelMixin
):
    queryset = models.Erc721SellOrder.objects.filter(cancelled=False)
    serializer_class = serializers.SellOrderSerializer

    def create(self, request, *args, **kwargs):
        assert request.data, "This request has no data"
        order = request.data.get("order")
        order_hash = request.data.get("orderHash")
        if not order or not order_hash:
            return Response(status=400)

        try:
            validate_seaport_sell_order(order, order_hash)
        except SignatureValidationFailed:
            return Response(status=400)

        address = order["parameters"]["offer"][0]["token"]
        token_id = order["parameters"]["offer"][0]["identifierOrCriteria"]
        smart_contract = get_object_or_404(
            models.Contract, address=address, approved=True, collection__approved=True
        )
        token = get_object_or_404(
            models.Erc721Token, smart_contract=smart_contract, token_id=token_id
        )
        seller = order["parameters"]["offerer"]

        start_time = datetime.fromtimestamp(
            int(order["parameters"]["startTime"]), timezone.utc
        )
        expiration = datetime.fromtimestamp(
            int(order["parameters"]["endTime"]), timezone.utc
        )
        price_gwei = sum(
            int(item["startAmount"]) for item in order["parameters"]["consideration"]
        ) / (10**9)
        quantity = 1
        signature = order["signature"]
        payment_token_addr = order["parameters"]["consideration"][0]["token"]
        payment_token = get_object_or_404(
            models.PaymentToken, address=payment_token_addr
        )

        order_json = json.dumps(order)

        try:
            sell_order = create_seaport_sell_order(
                token,
                seller,
                start_time,
                expiration,
                price_gwei,
                quantity,
                signature,
                payment_token.symbol,
                order_json,
                order_hash,
            )
        except Exception as e:
            if "Price must be lower than existing listing" in str(e):
                return Response(status=400)
            else:
                raise e

        serializer = self.get_serializer(sell_order)
        return Response(serializer.data)

    def list(self, request, *args, **kwargs):
        collectionAddress = request.query_params.get("collectionAddress")
        sellerAddress = request.query_params.get("sellerAddress")
        tokenId = request.query_params.get("tokenId")

        smart_contract = models.Contract.objects.get(address=collectionAddress)
        token = models.Erc721Token.objects.get(
            smart_contract=smart_contract, token_id=tokenId
        )
        seller_profile = models.Profile.objects.get(address=sellerAddress)
        sell_orders = models.Erc721SellOrder.objects.filter(
            token=token, seller=seller_profile, active=True
        )

        serializer = self.get_serializer(sell_orders, many=True)
        return Response(serializer.data)

    @action(
        detail=False,
        url_path="get-timestamps",
        methods=["GET"],
        permission_classes=[AllowAny],
    )
    def create_timestamps(self, request, *args, **kwargs):
        duration = request.query_params.get("duration")
        start_time, end_time = create_timestamps(duration)
        data = {"startTime": str(start_time), "endTime": str(end_time)}
        return Response(data=data)


class Erc721BuyOrderViewset(
    viewsets.GenericViewSet, mixins.RetrieveModelMixin, mixins.CreateModelMixin
):
    queryset = models.Erc721BuyOrder.objects.filter(cancelled=False)
    serializer_class = serializers.BuyOrderSerializer

    def create(self, request, *args, **kwargs):
        assert request.data, "This request has no data"
        order = request.data.get("order")
        order_hash = request.data.get("orderHash")
        if not order or not order_hash:
            return Response(status=400)

        try:
            validate_seaport_buy_order(order, order_hash)
        except SignatureValidationFailed:
            return Response(status=400)

        address = order["parameters"]["consideration"][0]["token"]
        token_id = order["parameters"]["consideration"][0]["identifierOrCriteria"]
        smart_contract = get_object_or_404(
            models.Contract, address=address, approved=True, collection__approved=True
        )
        token = get_object_or_404(
            models.Erc721Token, smart_contract=smart_contract, token_id=token_id
        )
        buyer = order["parameters"]["offerer"]

        start_time = datetime.fromtimestamp(
            int(order["parameters"]["startTime"]), timezone.utc
        )
        expiration = datetime.fromtimestamp(
            int(order["parameters"]["endTime"]), timezone.utc
        )
        price_gwei = sum(
            int(item["startAmount"]) for item in order["parameters"]["offer"]
        ) / (10**9)
        quantity = 1
        signature = order["signature"]

        payment_token_addr = order["parameters"]["offer"][0]["token"]
        payment_token = get_object_or_404(
            models.PaymentToken, address=payment_token_addr
        )

        order_json = json.dumps(order)

        try:
            buy_order = create_seaport_buy_order(
                token,
                buyer,
                start_time,
                expiration,
                price_gwei,
                quantity,
                signature,
                payment_token.symbol,
                order_json,
                order_hash,
            )
        except Exception as e:
            if "too many active offers" in str(e):
                return Response(data={"error": "too many active offers"}, status=400)
            if "duration must be" in str(e):
                return Response(status=400)
            else:
                raise e

        serializer = self.get_serializer(buy_order)
        return Response(serializer.data)

    @action(detail=False, url_path="get-buy-orders-for-token", methods=["GET"])
    def get_buy_orders_for_token(self, request, *args, **kwargs):
        token_str = request.query_params.get("token")
        address, token_id = token_str.split(":")
        try:
            address = Web3.toChecksumAddress(address)
        except Exception:
            return Response(status=status.HTTP_404_NOT_FOUND)

        smart_contract = get_object_or_404(
            models.Contract, address=address, approved=True, collection__approved=True
        )
        token = get_object_or_404(
            models.Erc721Token, smart_contract=smart_contract, token_id=token_id
        )

        buy_orders = token.erc721buyorder_set.all()
        page = self.paginate_queryset(buy_orders)
        serializer = serializers.BuyOrderSerializerShort(page, many=True)
        return self.get_paginated_response(serializer.data)


class CollectionViewset(viewsets.GenericViewSet):
    queryset = models.Erc721Collection.objects.filter(approved=True)
    serializer_class = serializers.CollectionSerializer
    lookup_field = "address"

    @method_decorator(cache_page(60))  # 1 minute
    def list(self, request, *args, **kwargs):
        collections = (
            self.queryset.filter(delisted=False, is_spam=False)
            .exclude(name__isnull=True)
            .exclude(name__exact="")
            .order_by("-volume", "verified")
        )
        collections = self.paginate_queryset(collections)
        serializer = serializers.CollectionSerializerForSearch(collections, many=True)
        return self.get_paginated_response(serializer.data)

    @method_decorator(cache_page(60))  # 1 minute
    def retrieve(self, request, address, *args, **kwargs):
        network = request.query_params.get("network")

        if network and network != NETWORK:
            try:
                smart_contract = models.Contract.objects.get(
                    address=address, network__network_id=network, approved=True
                )
            except models.Contract.DoesNotExist:
                return Response(status=status.HTTP_404_NOT_FOUND)
        else:
            smart_contract = get_or_create_contract(address=address, approved_only=True)

        if smart_contract:
            collection = smart_contract.collection
            serializer = self.serializer_class(collection)
            return Response(serializer.data)

        # Look up colleciton directly by URL slug
        try:
            collection = self.queryset.get(slug=address)
            serializer = self.serializer_class(collection)
            return Response(serializer.data)
        except models.Erc721Collection.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

    @method_decorator(cache_page(60 * 5))  # 5 minutes
    @action(detail=False, url_path="explore", methods=["GET"])
    def explore_collections(self, request, *args, **kwargs):
        col_ids = [
            col.id
            for col in self.queryset.filter(delisted=False, is_spam=False)
            if (col.volume > 0 or col.verified)
        ]
        collections = self.queryset.filter(id__in=col_ids).order_by("-volume_30d")
        collections = self.paginate_queryset(collections)
        serializer = serializers.CollectionSerializerMedium(collections, many=True)
        return self.get_paginated_response(serializer.data)

    @method_decorator(cache_page(60 * 5))  # 5 minutes
    @action(detail=False, url_path="launchpad", methods=["GET"])
    def launchpad_collections(self, request, *args, **kwargs):
        lp = HostedCollection.objects.filter(featured=True).values_list("address")
        collections = self.queryset.filter(address__in=lp).order_by("-id")
        page = self.paginate_queryset(collections)
        serializer = serializers.CollectionSerializerMedium(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, url_path="attributes", methods=["GET"])
    def attributes(self, request, address, *args, **kwargs):
        collection = get_object_or_404(self.queryset, address=address)
        serializer = serializers.CollectionAttributesSerializer(collection)
        return Response(serializer.data)

    # ================ COLLECTION ACTIVITY ================

    @method_decorator(cache_page(30))  # 30 seconds
    @action(detail=True, url_path="activity", methods=["GET"])
    def activity(self, request, address, *args, **kwargs):
        collection = get_object_or_404(self.queryset, address=address)

        events = request.query_params.getlist("event")
        sort_tags = request.query_params.getlist("activity_sort")
        chains = request.query_params.getlist("chain")
        attributes = request.query_params.getlist("attribute")
        price = request.query_params.get("price")
        payment_token = request.query_params.get("currency")
        intersect_attributes = (
            True if request.query_params.get("intersect_attributes") else False
        )

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
                    intersect_attributes,
                )
            except Exception as e:
                print(e)
                return Response(status=status.HTTP_400_BAD_REQUEST)
        else:
            activities = collection.activity()

        activities = self.paginate_queryset(activities)
        serializer = serializers.OnChainActivitySerializer(activities, many=True)
        return self.get_paginated_response(serializer.data)

    # ================ COLLECTION TOKENS ================

    @method_decorator(cache_page(5))  # 5 seconds
    @action(
        detail=True,
        url_path="tokens",
        methods=["GET"],
        pagination_class=QuixCollectionPaginator,
    )
    def tokens(self, request, address, *args, **kwargs):
        collection = get_object_or_404(self.queryset, address=address)

        attributes = (
            request.query_params.getlist("attribute")
            if request.query_params.get("attribute")
            else []
        )
        sort_tags = (
            request.query_params.getlist("sort")
            if request.query_params.get("sort")
            else []
        )
        chains = (
            request.query_params.getlist("chain")
            if request.query_params.get("chain")
            else []
        )
        availability = request.query_params.get("availability")
        price = request.query_params.get("price")
        payment_token = request.query_params.get("currency")
        search_query = request.query_params.get("query")
        intersect_attributes = (
            True if request.query_params.get("intersect_attributes") else False
        )

        if availability == "all":
            availability = False

        if payment_token == "all":
            payment_token = False

        if search_query:
            tokens = search_collection_tokens(search_query, collection)
        elif (
            attributes or sort_tags or availability or price or payment_token or chains
        ):
            if not sort_tags:
                sort_tags = ["price:asc"]

            try:
                tokens = collection_token_filters(
                    attributes,
                    sort_tags,
                    availability,
                    price,
                    payment_token,
                    chains,
                    collection.id,
                    intersect_attributes,
                    is_erc721_collection=collection.type == "721",
                )
            except Exception as e:
                print(e)
                return Response(status=status.HTTP_400_BAD_REQUEST)
        else:
            tokens = collection.erc721token_set.filter(approved=True)

            if NULL_PROFILE_INTERNAL_ID:
                tokens = tokens.exclude(owner__id=NULL_PROFILE_INTERNAL_ID)

            else:
                tokens = tokens.exclude(
                    owner__address="0x0000000000000000000000000000000000000000"
                )

            if BRIDGE_PROFILE_INTERNAL_ID:
                tokens = tokens.exclude(owner__id=BRIDGE_PROFILE_INTERNAL_ID)

            tokens = tokens.order_by("-for_sale", "price_eth", "id")

        tokens = tokens.prefetch_related("owner")

        tokens_page = self.paginate_queryset(tokens)
        collection_ctx = serializers.CollectionSerializerForToken(collection).data
        serializer = serializers.TokenSerializerForCollectionTokens(
            tokens_page, context={"collection_ctx": collection_ctx}, many=True
        )
        return self.get_paginated_response(serializer.data)

    # ================ COLLECTION STATS ================

    @method_decorator(cache_page(60 * 10))  # 10 minutes
    @action(detail=False, url_path="stats", methods=["GET"])
    def stats(self, request, *args, **kwargs):
        sort = request.query_params.get("sort")
        range = request.query_params.get("range")

        if not sort:
            sort = "volume:desc"
        if not range:
            range = "all"

        split_tag = sort.split(":")
        assert (
            split_tag[1].lower() == "asc" or split_tag[1].lower() == "desc"
        ), "Not a valid sort tag"

        if split_tag[1] == "desc":
            reverse = True
        else:
            reverse = False

        if range == "24h":
            col_ids = [
                col.id
                for col in self.queryset.filter(delisted=False)
                if col.volume_24h > 0
            ]
        elif range == "7d":
            col_ids = [
                col.id
                for col in self.queryset.filter(delisted=False)
                if col.volume_7d > 0
            ]
        elif range == "30d":
            col_ids = [
                col.id
                for col in self.queryset.filter(delisted=False)
                if col.volume_30d > 0
            ]
        else:
            col_ids = [
                col.id for col in self.queryset.filter(delisted=False) if col.volume > 0
            ]

        col_ids = [
            col_id for col_id in col_ids if col_id != 5769
        ]  # Exclude Dragonic Egg

        collections = self.queryset.filter(id__in=col_ids)

        if split_tag[0] == "volume":
            order = "volume"
            if reverse:
                order = "-" + order

            if range == "24h":
                order = order + "_" + range
            elif range == "7d":
                order = order + "_" + range
            elif range == "30d":
                order = order + "_" + range

            collections = self.paginate_queryset(collections.order_by(order))
        elif split_tag[0] == "volume_24h":
            collections = self.paginate_queryset(
                sorted(
                    collections,
                    key=lambda c: (
                        c.volume_change_24h() is not None,
                        c.volume_change_24h(),
                    ),
                    reverse=reverse,
                )
            )
        elif split_tag[0] == "volume_7d":
            collections = self.paginate_queryset(
                sorted(
                    collections,
                    key=lambda c: (
                        c.volume_change_7d() is not None,
                        c.volume_change_7d(),
                    ),
                    reverse=reverse,
                )
            )
        elif split_tag[0] == "floor":
            order = "floor"
            if reverse:
                collections = self.paginate_queryset(
                    collections.order_by(F(order).desc(nulls_last=True))
                )
            else:
                collections = self.paginate_queryset(
                    collections.order_by(F(order).asc(nulls_last=True))
                )
        elif split_tag[0] == "sales":
            order = "sales"
            if reverse:
                order = "-" + order

            if range == "24h":
                order = order + "_" + range
            elif range == "7d":
                order = order + "_" + range
            elif range == "30d":
                order = order + "_" + range

            collections = self.paginate_queryset(collections.order_by(order))
        elif split_tag[0] == "items":
            order = "supply"
            if reverse:
                order = "-" + order
            collections = self.paginate_queryset(collections.order_by(order))
        elif split_tag[0] == "listed":
            order = "listed"
            if reverse:
                order = "-" + order
            collections = self.paginate_queryset(collections.order_by(order))
        elif split_tag[0] == "owners":
            order = "owners"
            if reverse:
                order = "-" + order
            collections = self.paginate_queryset(collections.order_by(order))

        if range == "24h":
            serializer = serializers.CollectionSerializerForStats24H(
                collections, many=True
            )
        elif range == "7d":
            serializer = serializers.CollectionSerializerForStats7D(
                collections, many=True
            )
        elif range == "30d":
            serializer = serializers.CollectionSerializerForStats30D(
                collections, many=True
            )
        else:
            serializer = serializers.CollectionSerializerForStats(
                collections, many=True
            )
        return self.get_paginated_response(serializer.data)

    @action(detail=True, url_path="daily-stats", methods=["GET"])
    def daily_stats(self, request, address):
        collection = get_object_or_404(self.queryset, address=address)
        daily_stats = collection.daily_stats()
        return Response(data=daily_stats, status=200)

    # ================ COLLECTION SETTING ================

    @action(detail=True, url_path="settings", methods=["GET"])
    def collection_settings(self, request, address, *args, **kwargs):
        network = request.query_params.get("network")

        if network:
            smart_contract = get_object_or_404(
                models.Contract,
                address=address,
                network__network_id=network,
                approved=True,
                collection__approved=True,
            )
        else:
            smart_contract = get_or_create_contract(address=address, approved_only=True)

        if smart_contract:
            collection = smart_contract.collection
            serializer = serializers.CollectionSerializerForSettings(collection)
            return Response(serializer.data)

        return Response(status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, url_path="refresh-campaign", methods=["GET"])
    def refresh_campaign(self, request, address, *args, **kwargs):
        network = request.query_params.get("network")

        if network:
            smart_contract = get_object_or_404(
                models.Contract,
                address=address,
                network__network_id=network,
                approved=True,
                collection__approved=True,
            )
        else:
            smart_contract = get_or_create_contract(address=address, approved_only=True)

        if smart_contract:
            collection = smart_contract.collection

            try:
                collection.rewardscampaign.refresh_campaign()
            except Exception as e:
                print(e)
                return Response(status=status.HTTP_404_NOT_FOUND)

            serializer = serializers.CollectionSerializerForSettings(collection)
            return Response(serializer.data)

        return Response(status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, url_path="update-collection-royalties", methods=["POST"])
    def update_collection_royalties(self, request, address):
        message = request.data.get("message")
        signature = request.data.get("signature")

        if not message or not signature:
            return Response(data={"error": "message not signed"}, status=400)

        collection = get_object_or_404(self.queryset, address=address)
        if not verify_collection_signature(
            message, signature, collection.owner.address
        ):
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        else:
            print("Passed signing challenge")

        try:
            payout_address = Web3.toChecksumAddress(request.data.get("fee_recipient"))
            royalty_per_mille = int(request.data.get("royalty_per_mille"))

            if royalty_per_mille > 150:
                return Response(data={"error": "exceeded max royalties"}, status=400)

            collection.payout_address = payout_address
            collection.royalty_per_mille = royalty_per_mille

            collection.save()
            return Response(status=200)
        except Exception as e:
            return Response(status=500)

    @action(detail=True, url_path="update-collection-settings", methods=["POST"])
    def update_collection_settings(self, request, address):
        try:
            check_request_body(request)
        except UnsafeInputException:
            return Response(status=400)

        message = request.data.get("message")
        signature = request.data.get("signature")

        if not message or not signature:
            return Response(data={"error": "message not signed"}, status=400)

        collection = get_object_or_404(self.queryset, address=address)
        if not verify_collection_signature(
            message, signature, collection.owner.address
        ):
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        else:
            print("Passed signing challenge")

        try:
            collection.slug = (
                request.data.get("slug").lower() if request.data.get("slug") else None
            )
            collection.name = request.data.get("name")
            collection.description = request.data.get("description")
            collection.twitter_link = request.data.get("twitter_link")
            collection.site_link = request.data.get("site_link")
            collection.discord_link = request.data.get("discord_link")
            collection.category = request.data.get("category")
            collection.display_theme = request.data.get("display_theme")

            if request.data.get("ranking_enabled") == "true":
                if collection.ranking_enabled == False:
                    collection.refresh_ranks()
                    collection.ranking_enabled = True
            else:
                collection.ranking_enabled = False

            profile_image = request.data.get("profile_image")
            if profile_image:
                collection.profile_image = profile_image
            elif request.data.get("shouldDeleteImage") == "true":
                collection.profile_image = None

            cover_image = request.data.get("cover_image")
            if cover_image:
                collection.cover_image = cover_image
            elif request.data.get("shouldDeleteCoverImage") == "true":
                collection.cover_image = None

            collection.save()
            return Response(status=200)
        except Exception as e:
            if str(e).startswith("UNIQUE constraint failed") or str(e).startswith(
                "duplicate key value violates unique constraint"
            ):
                return Response(data={"error": "custom link already taken"}, status=400)
            else:
                return Response(status=500)


class SearchViewset(viewsets.GenericViewSet):
    @method_decorator(cache_page(60 * 10))  # 10 minutes
    def list(self, request):
        search_term = request.query_params.get("term")
        profiles = search_profiles(search_term, 4)
        collections = search_collections(search_term, 4)

        collections_serializer = serializers.CollectionSerializerForSearch(
            collections, many=True
        )
        profiles_serializer = serializers.ProfileSerializerForSearch(
            profiles, many=True
        )

        data = {
            "collections": collections_serializer.data,
            "profiles": profiles_serializer.data,
        }
        return Response(data, status=200)

    @method_decorator(cache_page(60 * 10))  # 10 minutes
    @action(detail=False, url_path="extended", methods=["GET"])
    def extended_search(self, request):
        search_term = request.query_params.get("term")
        profiles = search_profiles(search_term, 20)
        collections = search_collections(search_term, 20)
        # tokens = search_tokens(search_term, 20)

        # tokens_serializer = serializers.TokenSerializerMedium(tokens, many=True)
        collections_serializer = serializers.CollectionSerializerMedium(
            collections, many=True
        )
        profiles_serializer = serializers.ProfileSerializerForSearch(
            profiles, many=True
        )

        data = {
            "collections": collections_serializer.data,
            "profiles": profiles_serializer.data,
            "tokens": [],
        }
        return Response(data, status=200)


class Erc721BridgeViewset(viewsets.ReadOnlyModelViewSet):
    @action(detail=False, url_path="get-l1-address", methods=["GET"])
    def getL1TokenForL2Token(self, request):
        address = request.query_params.get("l2Address")
        try:
            address = Web3.toChecksumAddress(address)
            contract = L2Erc721Contract(address)
            remote_token = contract.remote_token()
            return Response(data={"address": remote_token})
        except Exception as e:
            print(e)
            return Response(status=400)

    @action(detail=False, url_path="get-l2-address", methods=["GET"])
    def getL2TokenForL1Token(self, request):
        address = request.query_params.get("l1Address")
        network_id = "eth-" + NETWORK[4:]

        try:
            address = Web3.toChecksumAddress(address)
            contract = models.Contract.objects.get(
                address=address, network__network_id=network_id
            )
            bridge_relationship = models.BridgedContract.objects.get(
                from_contract=contract, approved=True
            )
            return Response(data={"address": bridge_relationship.to_contract.address})
        except Exception:
            return Response(status=404)

    @action(detail=False, url_path="initiate-contract", methods=["POST"])
    def initiateBridgedContract(self, request):
        # return Response(status=400)

        l1_address = request.query_params.get("l1Address")
        override_supply = request.query_params.get("override_supply")
        network_id = "eth-" + NETWORK[4:]

        try:
            l1_address = Web3.toChecksumAddress(l1_address)

            url = f"https://api.simplehash.com/api/v0/nfts/ethereum/{l1_address}"
            headers = {
                "X-API-KEY": ""
            }
            r = requests.get(url, headers=headers)
            res = json.loads(r.text)
            collection_metadata = res["nfts"][0]["collection"]
            verified = False
            marketplace_pages = collection_metadata["marketplace_pages"]
            for marketplace in marketplace_pages:
                if marketplace["marketplace_id"] == "opensea":
                    verified = marketplace["verified"]

            # Only deploy collections that are verified on OpenSea
            # if not verified:
            #     return Response(status=400)

        except Exception as e:
            print(e)
            return Response(status=404)

        try:
            contract = models.Contract.objects.get(
                address=l1_address, network__network_id=NETWORK
            )
            return Response(status=400)
        except models.Contract.DoesNotExist:
            pass

        try:
            contract = Erc165Contract(l1_address, network_id=network_id)
        except Exception as e:
            print(e)
            return Response(status=400)

        if not contract.supports_721_interface():
            return Response(status=400)

        try:
            contract = Erc721Contract(l1_address, network_id=network_id)
        except Exception as e:
            print(e)
            return Response(status=400)

        total_supply = contract.totalSupply()
        if not override_supply and (not total_supply or total_supply > 15000):
            return Response(status=400)

        l1_contract = get_or_create_contract(
            address=l1_address, approved_only=True, network=network_id
        )
        if not l1_contract or l1_contract.type != models.CollectionType.ERC721:
            return Response(status=400)
        try:
            # If bridge relationship already exists, don't do anything
            models.BridgedContract.objects.get(from_contract=l1_contract)
            return Response(status=200)
        except models.BridgedContract.DoesNotExist as e:
            print(e)
            try:
                factory_contract = Erc721Factory()
                tx = factory_contract.deploy_contract(l1_address)
            except Exception as e:
                print(e)
                return Response(status=500)

            l2_address = "0x" + tx["logs"][0]["topics"][1].hex()[-40:]
            l2_address = Web3.toChecksumAddress(l2_address)
            l2_contract = models.Contract.objects.create(
                address=l2_address,
                collection=l1_contract.collection,
                approved=True,
                is_bridged=True,
            )

            models.BridgedContract.objects.create(
                from_contract=l1_contract, to_contract=l2_contract
            )

            l2_contract.refresh_contract()
            return Response(status=200)


class FeaturedViewset(viewsets.ReadOnlyModelViewSet):
    @method_decorator(cache_page(60 * 5))  # 5 minutes
    def list(self, request, *args, **kwargs):
        collections = []
        limit = 6
        featured_collections = models.FeaturedCollection.objects.order_by("id")[:limit]
        for col in featured_collections:
            collections.append(col.collection)
            limit = limit - 1

        featured_ids = [col.id for col in collections]
        all_collections = (
            models.Erc721Collection.objects.filter(
                approved=True, delisted=False, is_spam=False
            )
            .exclude(id__in=featured_ids)
            .exclude(id=5769)
            .order_by("-volume_7d")[:limit]
        )
        for col in all_collections:
            collections.append(col)

        featured_tokens = []
        # try:
        #     for col in collections:
        #         token_ids = models.Erc721Token.objects.filter(
        #             for_sale=True, collection=col
        #         ).values_list("id", flat=True)
        #         random_token_ids = sample(list(token_ids), min(len(token_ids), 2))
        #         random_tokens = list(
        #             models.Erc721Token.objects.filter(id__in=random_token_ids)
        #         )
        #         featured_tokens += random_tokens

        #     shuffle(featured_tokens)
        # except Exception:
        #     featured_tokens = []

        tokens_serializer = serializers.TokenSerializer(featured_tokens, many=True)
        collections_serializer = serializers.CollectionSerializerMedium(
            collections, many=True
        )

        if NETWORK == "opt-mainnet":
            mirror_addresses = [
                "0x1ad641eCdeaF065FaE8c7087AA121c3A569A29b7",
                "0xA95579592078783B409803Ddc75Bb402C217A924",
                "0xB7eE42A295BCC8CaEBEA298d3c3473d97c8FA16D",
                "0xC513f6c92A1B4726DA5B24cb786FE2B8bD6464f3",
            ]
            mirror_collections = models.Erc721Collection.objects.filter(
                address__in=mirror_addresses
            ).order_by("id")
            mirror_serializer = serializers.CollectionSerializerMedium(
                mirror_collections, many=True
            )

            opog_addresses = [
                "0x0110Bb5739a6F82eafc748418e572Fc67d854a0F",
                "0xBf2794ADAF7A48A2a24EB344a7bA221A52fe2171",
                "0x5a72C065DFE67D1C4e2951Fff292b8714a98CF68",
            ]
            opog_collections = models.Erc721Collection.objects.filter(
                address__in=opog_addresses
            ).order_by("-volume")
            opog_serializer = serializers.CollectionSerializerMedium(
                opog_collections, many=True
            )

            data = {
                "tokens": tokens_serializer.data,
                "collections": collections_serializer.data,
                "mirror": mirror_serializer.data,
                "opog": opog_serializer.data,
            }
        else:
            data = {
                "tokens": tokens_serializer.data,
                "collections": collections_serializer.data,
            }

        return Response(data)


class SiteBannerViewset(viewsets.ReadOnlyModelViewSet):
    def list(self, request, *args, **kwargs):
        banners = get_object_or_404(models.SiteBanner.objects.filter(active=True))
        banners_serializer = serializers.SiteBannerSerializer(banners)
        return Response(banners_serializer.data)


class HostedCollectionViewset(viewsets.GenericViewSet):
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        identifier = request.data.get("address")
        name = request.data.get("name")
        try:
            address = Web3.toChecksumAddress(identifier)
            models.HostedCollection.objects.create(address=address, name=name)
        except Exception as e:
            return Response(status=status.HTTP_404_NOT_FOUND)

        return Response(status=status.HTTP_200_OK)

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
        collection = get_object_or_404(models.HostedCollection, address=address)
        metadata = get_object_or_404(
            models.HostedMetadata, collection=collection, token_id=token_id
        )

        serializer = serializers.HostedMetadataSerializer(metadata)
        return Response(serializer.data)


class TokenMetadataViewset(viewsets.GenericViewSet):
    def retrieve(self, request, pk, retry=False, *args, **kwargs):
        address, token_id = pk.split(":")
        layer = request.query_params.get("layer")

        try:
            token_id = int(token_id)
            address = Web3.toChecksumAddress(address)
        except Exception as e:
            print(e)
            return Response(status=status.HTTP_404_NOT_FOUND)

        if layer == "l2":
            smart_contract = get_object_or_404(
                models.Contract, address=address, network__network_id=NETWORK
            )
            token = get_object_or_404(
                models.Erc721Token, smart_contract=smart_contract, token_id=token_id
            )

            bridge_txn = None
            bridge_txn_timestamp = None
            if token.owner.address == "0x0000000000000000000000000000000000000000":
                activity = (
                    models.Erc721Activity.objects.filter(
                        token=token, event_type_short="BR"
                    )
                    .order_by("-timestamp")
                    .first()
                )
                if activity:
                    bridge_txn = activity.txn_id
                    bridge_txn_timestamp = activity.timestamp

            data = {
                "contract_name": smart_contract.collection.name,
                "contract_symbol": smart_contract.collection.symbol,
                "token_owner": token.owner.address,
                "token_name": token.name,
                "token_image": token.image,
                "animation_url": token.animation_url,
                "animation_type": smart_contract.collection.animation_url_type,
                "background_color": token.background_color,
                "bridge_txn": bridge_txn,
                "bridge_txn_timestamp": bridge_txn_timestamp,
            }
            return Response(data=data, status=200)

        if layer == "l1":
            network_id = "eth-" + NETWORK[4:]

            try:
                contract = Erc165Contract(address, network_id=network_id)
            except Exception as e:
                print(e)
                return Response(status=status.HTTP_404_NOT_FOUND)

            if contract.supports_721_interface():
                contract = Erc721Contract(address, network_id=network_id)
                contract_name = contract.name()
                contract_symbol = contract.symbol()
                token_owner = contract.owner_of(token_id)

                try:
                    token_metadata_uri = contract.token_uri(token_id)
                    if not token_metadata_uri:
                        token_metadata_uri = contract.base_uri() + f"/{token_id}"

                    token_metadata_uri = token_metadata_uri.replace(" ", "")
                    if token_metadata_uri.startswith("data:application/json;base64,"):
                        token_metadata_uri = token_metadata_uri.replace(
                            "data:application/json;base64,", ""
                        )
                        token_metadata = json.loads(
                            base64.b64decode(token_metadata_uri), strict=False
                        )
                    elif token_metadata_uri.startswith("ipfs://"):
                        token_metadata_uri = token_metadata_uri.replace(
                            "ipfs://", "https://quixotic.infura-ipfs.io/ipfs/"
                        )
                        r = requests.get(token_metadata_uri)
                        token_metadata = json.loads(r.text, strict=False)
                    else:
                        r = requests.get(token_metadata_uri)
                        token_metadata = json.loads(r.text, strict=False)
                except Exception as e:
                    print(e)
                    token_metadata = None

                if not token_metadata:
                    return Response(status=status.HTTP_404_NOT_FOUND)

                if token_metadata.get("name"):
                    token_name = token_metadata.get("name")
                else:
                    token_name = contract_name + " #" + str(token_id)

                if token_metadata.get("image"):
                    token_image = token_metadata.get("image")
                    if token_image.startswith("ipfs://"):
                        token_image = (
                            "https://quixotic.infura-ipfs.io/ipfs/"
                            + token_image[len("ipfs://") :]
                        )
                    elif token_image.startswith("https://gateway.pinata.cloud/"):
                        token_image = token_image.replace(
                            "https://gateway.pinata.cloud/",
                            "https://quixotic.infura-ipfs.io/",
                        )
                    elif token_image.startswith("https://ipfs.infura.io/"):
                        token_image = token_image.replace(
                            "https://ipfs.infura.io/",
                            "https://quixotic.infura-ipfs.io/",
                        )
                    elif token_image.startswith("https://ipfs.io/"):
                        token_image = token_image.replace(
                            "https://ipfs.io/",
                            "https://quixotic.infura-ipfs.io/",
                        )
                else:
                    token_image = None

                if token_metadata.get("animation_url"):
                    animation_url = token_metadata.get("animation_url")
                    if animation_url.startswith("ipfs://"):
                        animation_url = (
                            "https://quixotic.infura-ipfs.io/ipfs/"
                            + animation_url[len("ipfs://") :]
                        )
                    elif animation_url.startswith("https://gateway.pinata.cloud/"):
                        animation_url = animation_url.replace(
                            "https://gateway.pinata.cloud/",
                            "https://quixotic.infura-ipfs.io/",
                        )
                    elif token_image.startswith("https://ipfs.infura.io/"):
                        token_image = token_image.replace(
                            "https://ipfs.infura.io/",
                            "https://quixotic.infura-ipfs.io/",
                        )
                    elif token_image.startswith("https://ipfs.io/"):
                        token_image = token_image.replace(
                            "https://ipfs.io/",
                            "https://quixotic.infura-ipfs.io/",
                        )

                    response = requests.head(animation_url)
                    try:
                        content_type = response.headers["content-type"]
                        if content_type.startswith("image/"):
                            animation_type = "Image"
                        elif content_type.startswith("video/"):
                            animation_type = "Video"
                        elif content_type.startswith("audio/"):
                            animation_type = "Audio"
                        elif content_type.startswith("text/html"):
                            animation_type = "HTML"
                        else:
                            animation_type = "Model"
                    except Exception:
                        animation_type = "Model"
                else:
                    animation_url = None
                    animation_type = None

                if token_metadata.get("background_color"):
                    background_color = token_metadata.get("background_color")
                else:
                    background_color = None

                bridge_txn = None
                bridge_txn_timestamp = None
                if  token_owner == L2ERC721_BRIDGE:
                    bridge_relationship = models.BridgedContract.objects.get(
                        from_contract__address=address
                    )
                    smart_contract = bridge_relationship.to_contract
                    token = get_object_or_404(
                        models.Erc721Token,
                        smart_contract=smart_contract,
                        token_id=token_id,
                    )
                    activity = (
                        models.Erc721Activity.objects.filter(
                            token=token, event_type_short="BR"
                        )
                        .order_by("-timestamp")
                        .first()
                    )
                    if activity:
                        bridge_txn = activity.txn_id
                        bridge_txn_timestamp = activity.timestamp

                data = {
                    "contract_name": contract_name,
                    "contract_symbol": contract_symbol,
                    "token_owner": token_owner,
                    "token_name": token_name,
                    "token_image": token_image,
                    "animation_url": animation_url,
                    "animation_type": animation_type,
                    "background_color": background_color,
                    "bridge_txn": bridge_txn,
                    "bridge_txn_timestamp": bridge_txn_timestamp,
                }
                return Response(data=data, status=200)
            elif contract.supports_1155_interface():
                return Response(data={"error": "1155"}, status=400)
            else:
                return Response(status=status.HTTP_404_NOT_FOUND)


router = routers.DefaultRouter()
router.register("profile", ProfileViewset)
router.register("activity", Erc721ActivityViewset)
router.register("token", TokenViewset)
router.register("collection", CollectionViewset)
router.register("sellorder", Erc721SellOrderViewset)
router.register("buyorder", Erc721BuyOrderViewset)
router.register("search", SearchViewset, basename="search")
router.register("featured", FeaturedViewset, basename="featured")
router.register("banner", SiteBannerViewset, basename="banner")
router.register(
    "hosted-collection", HostedCollectionViewset, basename="hosted-collection"
)
router.register("token-metadata", TokenMetadataViewset, basename="token-metadata")
router.register("erc721bridge", Erc721BridgeViewset, basename="erc721bridge")
