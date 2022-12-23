from math import sqrt

from api.utils.constants import NETWORK, L2ERC721_BRIDGE
from django.contrib.postgres.search import TrigramWordSimilarity
from django.db.models.functions import Greatest
from web3 import Web3

from ..models import Erc721Collection, Erc721Token, Profile


def search_collections(text, limit):
    if text.startswith("0x") and len(text) == 42:
        try:
            address = Web3.toChecksumAddress(text)
            collections = Erc721Collection.objects.filter(address=address)
            return collections
        except Exception:
            pass

    collections = (
        Erc721Collection.objects.filter(approved=True, delisted=False)
        .annotate(similarity=TrigramWordSimilarity(text, "name"))
        .filter(similarity__isnull=False)
        .filter(similarity__gte=0.3)
    )

    for col in collections:
        col.relevance = (0.9 * col.similarity) * (
            0.1 * sqrt(col.volume / (10**9) + 1)
        )

    return sorted(collections, key=lambda c: c.relevance, reverse=True)[:limit]


def search_profiles(text, limit):
    if text.startswith("0x") and len(text) == 42:
        try:
            address = Web3.toChecksumAddress(text)
            profiles = Profile.objects.filter(address=address)
            return profiles
        except Exception:
            pass

    profiles = (
        Profile.objects.annotate(
            ens_similarity=TrigramWordSimilarity(text, "reverse_ens")
        )
        .annotate(username_similarity=TrigramWordSimilarity(text, "username"))
        .annotate(similarity=Greatest("ens_similarity", "username_similarity"))
        .filter(similarity__isnull=False)
        .filter(similarity__gte=0.3)
        .order_by("-similarity")[:limit]
    )

    return profiles


def search_profile_tokens(text, profile):
    token_ids = []
    tokens = profile.tokens()
    for token in tokens:
        token_ids.append(token.id)

    tokens = (
        Erc721Token.objects.filter(id__in=token_ids)
        .annotate(name_similarity=TrigramWordSimilarity(text, "name"))
        .annotate(collection_similarity=TrigramWordSimilarity(text, "collection__name"))
        .annotate(similarity=Greatest("name_similarity", "collection_similarity"))
        .filter(similarity__isnull=False)
        .filter(similarity__gte=0.3)
        .order_by("-similarity")
    )

    return tokens


def search_collection_tokens(text, collection):
    tokens = (
        Erc721Token.objects.filter(approved=True, collection=collection)
        .exclude(owner__address=L2ERC721_BRIDGE)
        .annotate(similarity=TrigramWordSimilarity(text, "name"))
        .filter(similarity__isnull=False)
        .filter(similarity__gte=0.3)
        .order_by("-similarity")
    )

    return tokens


def search_tokens(text, limit):
    tokens = (
        Erc721Token.objects.filter(approved=True)
        .exclude(owner__address=L2ERC721_BRIDGE)
        .annotate(similarity=TrigramWordSimilarity(text, "name"))
        .filter(similarity__isnull=False)
        .filter(similarity__gte=0.6)
        .order_by("-similarity")[:limit]
    )

    return tokens
