from rest_framework import routers, viewsets, status, mixins
from rest_framework.decorators import action
from .utils.refresh_all_owners_for_collection import refresh_all_owners_for_collection
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser

from api.models import Erc721Collection
from django.shortcuts import get_object_or_404
from celery import group


class CollectionBatchProcessingViewset(viewsets.GenericViewSet):
    lookup_field = "address"
    permission_classes = [IsAdminUser]

    @action(detail=True, url_path="refresh-all-token-owners", methods=["POST"])
    def refresh_all_token_owners(self, request, address, *args, **kwargs):
        refresh_all_owners_for_collection(address)
        return Response()


router = routers.DefaultRouter()
router.register('collection', CollectionBatchProcessingViewset, basename="collection")
