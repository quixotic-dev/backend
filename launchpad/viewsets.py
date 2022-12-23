from rest_framework.response import Response
from rest_framework import routers, viewsets, status, mixins
from .utils.launchpad_factory import create_launchpad_contract
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from django.shortcuts import get_object_or_404
from web3 import Web3
from . import models, serializers
from api.utils.signature_utils import verify_collection_signature
from api.models import Erc721Collection
import json


class LaunchPadContractViewset(viewsets.GenericViewSet):
    lookup_field = "address"

    @action(detail=False, url_path="create", methods=["POST"])
    def create_contract(self, request, *args, **kwargs):
        init = request.data
        abi, bytecode, src = create_launchpad_contract(init)
        data = {
            "abi": abi,
            "bytecode": bytecode,
            "src": src,
        }
        return Response(data=data)

    @action(detail=True, url_path="green-list-mint", methods=["GET"])
    def green_list_mint(self, request, address, *args, **kwargs):
        collection = get_object_or_404(models.HostedCollection, address=address)
        address = request.query_params.get("address")

        greenlist_address = get_object_or_404(
            models.GreenlistedAddress, address=address, collection=collection
        )
        data = {"signature": greenlist_address.get_signature()}
        return Response(data=data)


class HostedCollectionViewset(
    viewsets.GenericViewSet,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
):
    queryset = models.HostedCollection.objects.all()
    serializer_class = serializers.HostedCollectionSerializer
    lookup_field = "address"

    def create(self, request, *args, **kwargs):
        address = request.data.get("address")
        src = request.data.get("src")
        name = request.data.get("name")
        max_supply = request.data.get("max_supply")
        premint_price = request.data.get("premint_price")
        mint_price = request.data.get("mint_price")
        max_per_premint = request.data.get("max_per_premint")
        max_per_mint = request.data.get("max_per_mint")
        reserve_tokens = request.data.get("reserve_tokens")

        try:
            address = Web3.toChecksumAddress(address)
            collection = models.HostedCollection.objects.create(address=address)
            collection.src_code = src
            collection.name = name
            collection.max_supply = max_supply
            collection.premint_price = premint_price
            collection.mint_price = mint_price
            collection.max_per_mint = max_per_mint

            if premint_price and max_per_premint:
                collection.max_per_premint = max_per_premint
                collection.premint = True

            if reserve_tokens:
                collection.reserve_tokens = True

            collection.save()

        except Exception as e:
            print(e)
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(status=status.HTTP_200_OK)

    def retrieve(self, request, address, *args, **kwargs):
        if address.startswith("0x"):
            address = Web3.toChecksumAddress(address)
            collection = get_object_or_404(models.HostedCollection, address=address)
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = self.serializer_class(collection)
        return Response(serializer.data)

    @action(detail=True, url_path="greenlist", methods=["GET"])
    def greenlist(self, request, address):
        if address.startswith("0x"):
            address = Web3.toChecksumAddress(address)
            collection = get_object_or_404(models.HostedCollection, address=address)
            addresses = models.GreenlistedAddress.objects.filter(collection=collection)
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)

        page = self.paginate_queryset(addresses)
        serializer = serializers.GreenlistedAddressSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, url_path="update-greenlist", methods=["POST"])
    def update_greenlist(self, request, address):
        message = request.data.get("message")
        signature = request.data.get("signature")

        assert message is not None, "Missing form field 'message' in data"
        assert signature is not None, "Missing form field 'signtature' in data"

        collection = get_object_or_404(Erc721Collection, address=address)
        if not verify_collection_signature(
            message, signature, collection.owner.address
        ):
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        else:
            print("Passed signing challenge")

        address_list = json.loads(request.data.get("addresses"))
        hosted_collection = get_object_or_404(models.HostedCollection, address=address)

        for gl_address in address_list:
            if isinstance(gl_address, list):
                gl_address = gl_address[0]
            try:
                checksum_address = Web3.toChecksumAddress(gl_address)
                models.GreenlistedAddress.objects.create(
                    address=checksum_address, collection=hosted_collection
                )
            except Exception as e:
                print((str(e)))

        addresses = models.GreenlistedAddress.objects.filter(
            collection=hosted_collection
        )
        page = self.paginate_queryset(addresses)
        serializer = serializers.GreenlistedAddressSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, url_path="generate-metadata", methods=["POST"])
    def generate_metadata(self, request, address):
        message = request.data.get("message")
        signature = request.data.get("signature")

        assert message is not None, "Missing form field 'message' in data"
        assert signature is not None, "Missing form field 'signtature' in data"

        collection = get_object_or_404(Erc721Collection, address=address)
        if not verify_collection_signature(
            message, signature, collection.owner.address
        ):
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        else:
            print("Passed signing challenge")

        hosted_collection = models.HostedCollection.objects.get(address=address)
        hosted_collection.metadata_generated = True
        hosted_collection.save()

        for x in range(hosted_collection.max_supply):
            models.HostedMetadata.objects.update_or_create(
                token_id=x,
                collection=hosted_collection,
                description=collection.description,
                image=collection.profile_image,
            )

        return Response(status=200)

    @action(detail=True, url_path="update-metadata-uri", methods=["POST"])
    def generate_metadata(self, request, address):
        hosted_collection = get_object_or_404(models.HostedCollection, address=address)
        uri = request.query_params.get("uri")
        hosted_collection.base_uri = uri

        token_id = request.query_params.get("token_id")
        if token_id == "false":
            hosted_collection.base_uri_token_id = False
        elif token_id == "true":
            hosted_collection.base_uri_token_id = True

        extension = request.query_params.get("extension")
        if extension == "false":
            hosted_collection.base_uri_file_extension = False
        elif extension == "true":
            hosted_collection.base_uri_file_extension = True

        hosted_collection.save()
        return Response(status=200)

    @action(detail=True, url_path="refresh", methods=["PUT"])
    def refresh(self, request, address, *arg, **kwargs):
        if address.startswith("0x"):
            address = Web3.toChecksumAddress(address)
            collection = get_object_or_404(models.HostedCollection, address=address)
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)

        collection.refresh()
        serializer = self.serializer_class(collection)
        return Response(serializer.data)


class HostedMetadataViewset(viewsets.GenericViewSet):
    permission_classes = [AllowAny]

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

        if not metadata.active:
            metadata.refresh()

        if metadata.active:
            serializer = serializers.HostedMetadataSerializer(metadata)
            return Response(serializer.data)
        else:
            return Response(status=404)


router = routers.DefaultRouter()
router.register("contract", LaunchPadContractViewset, basename="contract")
router.register(
    "hosted-collection", HostedCollectionViewset, basename="hosted-collection"
)
router.register("hosted-metadata", HostedMetadataViewset, basename="contract-metadata")
