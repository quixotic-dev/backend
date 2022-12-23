import base64
import hashlib
import json
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
import boto3
import requests
from web3 import Web3
import yaml
from PIL import Image
from django.conf import settings

from api.models import (
    CollectionAnimationType,
    CollectionType,
    Erc721Token,
    Erc721TokenAttribute,
    Network,
)
from api.utils.Erc1155Contract import Erc1155Contract
from api.utils.Erc721Contract import Erc721Contract
from api.utils.constants import NETWORK
from api.utils.eip681_utils import parse_eip681_uri
from api.utils.text_utils import fix_smart_quotes, replace_links_with_markdown_links


def pull_collection_metadata(collection):
    if collection.type == CollectionType.ERC721:
        contract = Erc721Contract(
            collection.primary_contract.address,
            collection.primary_contract.network.network_id,
        )
    elif collection.type == CollectionType.ERC1155:
        contract = Erc1155Contract(
            collection.primary_contract.address,
            collection.primary_contract.network.network_id,
        )
    else:
        return

    metadata_uri = contract.contract_uri()
    if not metadata_uri:
        return

    ipfs_prefix = "ipfs://"
    if metadata_uri.startswith(ipfs_prefix):
        try:
            r = requests.get(
                f"https://quixotic.mypinata.cloud/ipfs/{metadata_uri[len(ipfs_prefix):]}"
            )
            metadata_str = r.text
            metadata = json.loads(metadata_str)
        except Exception:
            metadata = {}
    elif metadata_uri.startswith("data:application/json;base64"):
        try:
            prefix, msg = metadata_uri.split(",", 1)
            metadata = json.loads(base64.b64decode(msg))
        except Exception:
            metadata = {}
    else:
        try:
            r = requests.get(metadata_uri)
            metadata = json.loads(r.text)
        except Exception:
            return None

    return metadata


def pull_contract_image(collection, image_url, should_save=True):
    client = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )

    base_path = "https://fanbase-1.s3.amazonaws.com"
    ts = round(time.time())

    image_url_hash = hashlib.md5(image_url.encode("utf-8")).hexdigest()

    if (
        collection.profile_image_url
        and collection.profile_image_hash
        and collection.profile_image_hash == image_url_hash
        and collection.profile_image_url.startswith(base_path)
    ):
        print("Image url didn't change, so not pulling.")
    else:
        print(f"Pulling in media for {collection.name}")
        if image_url.startswith("data:"):
            if "data:" in image_url and ";base64," in image_url:
                header, data = image_url.split(";base64,")
            try:
                decoded_file = base64.b64decode(data)
                file_name = "image"
                aws_key = f"collection_image/{collection.address}/{ts}/{file_name}"
                client.upload_fileobj(
                    BytesIO(decoded_file),
                    settings.AWS_STORAGE_BUCKET_NAME,
                    aws_key,
                    ExtraArgs={"ContentType": header.split("data:")[1]},
                )
                collection.profile_image_url = f"{base_path}/{aws_key}"
                collection.profile_image_hash = image_url_hash
            except TypeError:
                TypeError("invalid_image")
        else:
            if image_url.startswith("ipfs://"):
                image_url = (
                    f"https://quixotic.infura-ipfs.io/ipfs/{image_url[len('ipfs://'):]}"
                )

            try:
                r = requests.get(image_url, stream=True)
            except Exception:
                return print(f"Invalid URL: {image_url}")

            if r.status_code >= 400:
                return print(f"The request returned a bad status code {r}")

            try:
                img_content = BytesIO(r.content)
                img = Image.open(img_content)
                format = img.format
                if format == "JPEG" or format == "PNG":
                    print(f"Image format: {format}, pulling")
                    img_content = BytesIO()
                    img.thumbnail((1000, 1000), Image.ANTIALIAS)
                    img.save(img_content, format=format, optimize=True, quality=75)
                    img_content.seek(0)

                    # file_name = urllib.parse.quote(Path(image_url).name)
                    if format == "JPEG":
                        file_name = "image.jpg"
                    elif format == "PNG":
                        file_name = "image.png"
                    aws_key = f"collection_image/{collection.address}/{ts}/{file_name}"
                    client.upload_fileobj(
                        BytesIO(r.content), settings.AWS_STORAGE_BUCKET_NAME, aws_key
                    )
                    collection.profile_image_url = f"{base_path}/{aws_key}"
                    collection.profile_image_hash = image_url_hash
                else:
                    print(f"Image format: {format}, skipping")
            except Exception as e:
                collection.profile_image_url = image_url
                collection.profile_image_hash = image_url_hash

    if should_save:
        collection.save()


def refresh_collection_metadata(collection, should_save=True):
    metadata = pull_collection_metadata(collection)
    if not metadata:
        return

    if metadata.get("name"):
        collection.name = metadata.get("name")

    if metadata.get("description") and not collection.description:
        description = fix_smart_quotes(metadata.get("description"))

        if not (
            "[" in description and "]" in description
        ):  # Quick check to see if it's kinda like markdown
            description = replace_links_with_markdown_links(description)

        collection.description = description

    if metadata.get("external_url"):
        collection.site_link = metadata.get("external_url")
    elif metadata.get("external_link"):
        collection.site_link = metadata.get("external_link")

    if metadata.get("image"):
        pull_contract_image(
            collection, image_url=metadata.get("image"), should_save=False
        )

    if metadata.get("fee_recipient") and metadata.get("seller_fee_basis_points"):
        if not collection.payout_address or not collection.royalty_per_mille:
            payout_address = Web3.toChecksumAddress(metadata.get("fee_recipient"))
            royalty_per_mille = min(
                int(metadata.get("seller_fee_basis_points")) / 10, 150
            )

            collection.payout_address = payout_address
            collection.royalty_per_mille = royalty_per_mille

    if should_save:
        collection.save()


def refresh_collection_animation_url_type(collection, should_save=True):
    first_token = (
        Erc721Token.objects.filter(collection=collection)
        .exclude(animation_url=None)
        .first()
    )

    if first_token and first_token.animation_url:
        response = requests.head(first_token.animation_url)
        if response.status_code == 302:
            response = requests.head(response.headers["Location"])

        if "content-type" in response.headers:
            content_type = response.headers["content-type"]
        elif "Content-Type" in response.headers:
            content_type = response.headers["Content-Type"]
        else:
            return

        print(content_type)

        if content_type.startswith("image/"):
            collection.animation_url_type = CollectionAnimationType.IMAGE
        elif content_type.startswith("video/"):
            collection.animation_url_type = CollectionAnimationType.VIDEO
        elif content_type.startswith("audio/"):
            collection.animation_url_type = CollectionAnimationType.AUDIO
        elif content_type.startswith("text/html"):
            collection.animation_url_type = None
            # collection.animation_url_type = CollectionAnimationType.HTML
        elif content_type.startswith("application/octet-stream"):
            collection.animation_url_type = CollectionAnimationType.MODEL
        elif content_type.startswith("application/json"):
            collection.animation_url_type = CollectionAnimationType.MODEL
        else:
            if not collection.animation_url_type:
                collection.animation_url_type = CollectionAnimationType.MODEL

        if should_save:
            collection.save()


def pull_token_metadata(token):
    if token.smart_contract.type == CollectionType.ERC721:
        contract = Erc721Contract(
            token.smart_contract.address,
            token.smart_contract.network.network_id,
        )
    elif token.smart_contract.type == CollectionType.ERC1155:
        contract = Erc1155Contract(
            token.smart_contract.address,
            token.smart_contract.network.network_id,
        )
    else:
        return

    try:
        metadata_uri = contract.token_uri(token.token_id)
    except Exception as e:
        print(e)
        try:
            metadata_uri = contract.base_uri() + f"/{token.token_id}"
        except Exception as e:
            print(e)
            return

    if not metadata_uri:
        try:
            metadata_uri = contract.base_uri() + f"/{token.token_id}"
        except Exception as e:
            print(e)
            return

    # Get native metadata URI if bridged NFT
    if metadata_uri.startswith("ethereum:"):
        try:
            address, chain_id, contract_method, arg_name, arg = parse_eip681_uri(
                metadata_uri
            )
            address = Web3.toChecksumAddress(address)
            if chain_id == "1" or chain_id == "5":
                redirected_contract = Erc721Contract(
                    address,
                    Network.objects.get(chain_id=hex(int(chain_id))).network_id,
                )
                tokenUriFunc = getattr(redirected_contract, contract_method)
                redirect_result_uri = tokenUriFunc(arg)
                metadata_uri = redirect_result_uri

                if not metadata_uri:
                    return
            else:
                raise Exception(f"Redirect not supported to chain {chain_id}")
        except Exception as e:
            print(e)
            return None

    # Replace {id} with token ID (part of ERC1155 metadata spec)
    if token.smart_contract.type == CollectionType.ERC1155:
        metadata_uri = metadata_uri.replace(
            "{id}", str(hex(int(token.token_id))[2:].zfill(64))
        )

    metadata_uri = metadata_uri.replace(" ", "")
    ipfs_prefix = "ipfs://"
    if metadata_uri.startswith(ipfs_prefix):
        try:
            if token.smart_contract.network.network_id != NETWORK:
                r = requests.get(
                    f"https://quixotic.infura-ipfs.io/ipfs/{metadata_uri[len(ipfs_prefix):]}"
                )
            else:
                r = requests.get(
                    f"https://quixotic.mypinata.cloud/ipfs/{metadata_uri[len(ipfs_prefix):]}"
                )
            metadata = json.loads(r.text, strict=False)
        except Exception as e:
            print(e)
            if str(e).startswith("Expecting property name enclosed in double quotes"):
                try:
                    metadata = yaml.safe_load(r.text)
                except Exception as e:
                    print(e)
                    return None
            else:
                return None
    elif metadata_uri.startswith("https://") or metadata_uri.startswith("http://"):
        try:
            if metadata_uri.startswith("https://gateway.pinata.cloud/"):
                metadata_uri = metadata_uri.replace(
                    "https://gateway.pinata.cloud/", "https://quixotic.infura-ipfs.io/"
                )
            elif metadata_uri.startswith("https://ipfs.infura.io/"):
                metadata_uri = metadata_uri.replace(
                    "https://ipfs.infura.io/", "https://quixotic.infura-ipfs.io/"
                )
            elif metadata_uri.startswith("https://ipfs.io/"):
                metadata_uri = metadata_uri.replace(
                    "https://ipfs.io/", "https://quixotic.infura-ipfs.io/"
                )
            r = requests.get(metadata_uri)
            metadata = json.loads(r.text, strict=False)
        except Exception as e:
            print(e)
            if str(e).startswith("Expecting property name enclosed in double quotes"):
                try:
                    metadata = yaml.safe_load(r.text)
                except Exception as e:
                    print(e)
                    return None
            else:
                return None
    elif metadata_uri.startswith("data:application/json;base64"):
        try:
            prefix, msg = metadata_uri.split(",", 1)
            metadata = json.loads(base64.b64decode(msg), strict=False)
        except Exception as e:
            print(e)
            return None
    else:
        try:
            metadata = json.loads(metadata_uri, strict=False)
        except Exception:
            return None

    return metadata


def refresh_token_metadata(token, should_save=True):
    metadata = pull_token_metadata(token)
    if not metadata:
        return

    try:
        if metadata.get("name"):
            token.name = str(metadata.get("name")).replace("\x00", "")

        if description := metadata.get("description"):
            description = fix_smart_quotes(description)

            if not (
                "[" in description and "]" in description
            ):  # Quick check to see if it's kinda like markdown
                description = replace_links_with_markdown_links(description)

            token.description = fix_smart_quotes(description)

        if metadata.get("background_color"):
            token.background_color = metadata.get("background_color").replace("#", "")

        if metadata.get("external_url"):
            token.external_url = metadata.get("external_url")
        elif metadata.get("external_link"):
            token.external_url = metadata.get("external_link")

        # Update image if the url has changed
        image_url = metadata.get("image")
        if image_url and (
            image_url.startswith("data:")
            or image_url.startswith("ipfs:")
            or image_url.startswith("http:")
            or image_url.startswith("https:")
        ):
            if image_url.startswith("ipfs://"):
                image_url = (
                    "https://quixotic.infura-ipfs.io/ipfs/"
                    + image_url[len("ipfs://") :]
                )
            elif image_url.startswith("https://gateway.pinata.cloud/"):
                image_url = image_url.replace(
                    "https://gateway.pinata.cloud/", "https://quixotic.infura-ipfs.io/"
                )
            elif image_url.startswith("https://ipfs.infura.io/"):
                image_url = image_url.replace(
                    "https://ipfs.infura.io/", "https://quixotic.infura-ipfs.io/"
                )
            elif image_url.startswith("https://ipfs.io/"):
                image_url = image_url.replace(
                    "https://ipfs.io/", "https://quixotic.infura-ipfs.io/"
                )

            image_url_hash = hashlib.md5(image_url.encode("utf-8")).hexdigest()
            if image_url_hash != token.image_src or not token.image:
                token.last_media_pull = None
                if len(image_url) <= 10000:
                    token.image = image_url
                    token.image_src = image_url_hash
                else:
                    token.pull_media(metadata=metadata, override_cooldown=True)
        else:
            token.image = None
            token.image_src = None

        # Update animation if the url has changed
        animation_url = metadata.get("animation_url")
        if animation_url and (
            animation_url.startswith("data:")
            or animation_url.startswith("ipfs:")
            or animation_url.startswith("http:")
            or animation_url.startswith("https:")
        ):
            if animation_url.startswith("ipfs://"):
                animation_url = (
                    "https://quixotic.infura-ipfs.io/ipfs/"
                    + animation_url[len("ipfs://") :]
                )
            elif animation_url.startswith("https://gateway.pinata.cloud/"):
                animation_url = animation_url.replace(
                    "https://gateway.pinata.cloud/", "https://quixotic.infura-ipfs.io/"
                )
            elif animation_url.startswith("https://ipfs.infura.io/"):
                animation_url = animation_url.replace(
                    "https://ipfs.infura.io/", "https://quixotic.infura-ipfs.io/"
                )
            elif animation_url.startswith("https://ipfs.io/"):
                animation_url = animation_url.replace(
                    "https://ipfs.io/", "https://quixotic.infura-ipfs.io/"
                )

            animation_url_hash = hashlib.md5(animation_url.encode("utf-8")).hexdigest()
            if animation_url_hash != token.animation_url_src or not token.animation_url:
                # Temporary fix to prevent errors, but ignores long animation URLs
                if len(animation_url) <= 10000:
                    token.last_media_pull = None
                    token.animation_url = animation_url
                    token.animation_url_src = animation_url_hash

                    if not token.collection.animation_url_type:
                        refresh_collection_animation_url_type(token.collection)
        else:
            token.animation_url = None
            token.animation_url_src = None

        if should_save:
            token.save()

        if attributes := metadata.get("attributes"):
            Erc721TokenAttribute.objects.filter(token=token).delete()
            for attribute in attributes:
                try:
                    if trait_type := attribute.get("trait_type"):
                        trait_type = fix_smart_quotes(trait_type)
                    if value := attribute.get("value"):
                        value = fix_smart_quotes(value)
                    else:
                        value = ""
                    if trait_type:
                        Erc721TokenAttribute.objects.create(
                            token=token, trait_type=trait_type, value=value
                        )
                except Exception as e:
                    continue
    except Exception as e:
        print(e)
        return


def pull_token_media(token, metadata=None, use_existing=False, override_cooldown=False):
    # Emergency fix for AWS errors
    emergency_exclusions = {
        "0x915d0d9e68CCa951B3A0aeD95f236Fff912431da",
        "0x2F71f4a2D8BAB9703fff3fF5794762bF5b6C7E29",
        "0xA95579592078783B409803Ddc75Bb402C217A924",
        "0xb5E89dc549B070CdD51fc18F1072aE9eC6e7A7C2",
    }
    if token.smart_contract.address in emergency_exclusions:
        return

    print(f"Pulling new media for token: {token}")
    cooldown_int = 12
    cooldown = timedelta(hours=cooldown_int)
    if (
        not override_cooldown
        and token.last_media_pull
        and token.last_media_pull + cooldown > datetime.now(tz=timezone.utc)
    ):
        print(f"You can only pull media once every {cooldown_int} hours")
        return

    token.last_media_pull = datetime.now(tz=timezone.utc)
    token.save()

    if use_existing:
        image_url = token.image
        animation_url = token.animation_url
    else:
        if not metadata:
            metadata = pull_token_metadata(token)
            if not metadata:
                print(f"No metadata to grab for {token}")
                return
        image_url = metadata.get("image")
        animation_url = metadata.get("animation_url")

    if not image_url and not animation_url:
        print(f"No media to pull for {token}")
        return

    client = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )

    base_path = "https://fanbase-1.s3.amazonaws.com"
    ts = round(time.time())

    if image_url and (
        image_url.startswith("data:")
        or image_url.startswith("ipfs:")
        or image_url.startswith("http:")
        or image_url.startswith("https:")
    ):
        if image_url.startswith("ipfs://"):
            image_url = (
                "https://quixotic.infura-ipfs.io/ipfs/" + image_url[len("ipfs://") :]
            )
        elif image_url.startswith("https://gateway.pinata.cloud/"):
            image_url = image_url.replace(
                "https://gateway.pinata.cloud/", "https://quixotic.infura-ipfs.io/"
            )
        elif image_url.startswith("https://ipfs.infura.io/"):
            image_url = image_url.replace(
                "https://ipfs.infura.io/", "https://quixotic.infura-ipfs.io/"
            )
        elif image_url.startswith("https://ipfs.io/"):
            image_url = image_url.replace(
                "https://ipfs.io/", "https://quixotic.infura-ipfs.io/"
            )

        image_url_hash = hashlib.md5(image_url.encode("utf-8")).hexdigest()
        if (
            token.image_src
            and token.image_src == image_url_hash
            and token.image
            and token.image.startswith(base_path)
        ):
            print("Image url didn't change, so not pulling.")
            return

        print(f"Fetching media for {token.name}")

        if image_url.startswith("data:"):
            if "data:" in image_url and ";base64," in image_url:
                header, data = image_url.split(";base64,")
            try:
                decoded_file = base64.b64decode(data)
                file_name = "image"
                file_extension = ".svg" if data[0] == "P" else ""
                file_name += file_extension
                aws_key = f"nft_image/{token.smart_contract.address}/{token.token_id}/{ts}/{file_name}"
                client.upload_fileobj(
                    BytesIO(decoded_file),
                    settings.AWS_STORAGE_BUCKET_NAME,
                    aws_key,
                    ExtraArgs={"ContentType": header.split("data:")[1]},
                )
                token.image = f"{base_path}/{aws_key}"
                token.image_src = image_url_hash
            except Exception as e:
                print(e)
                print(f"Invalid URL: {image_url}")
                return
        else:
            try:
                r = requests.get(image_url)
            except Exception:
                print(f"Invalid URL: {image_url}")
                token.image = None
                token.save()
                return

            if r.status_code >= 400:
                print(f"The request returned a bad status code {r}")
                return

            # Compress & store file if png or jpg image
            try:
                img_content = BytesIO(r.content)
                img = Image.open(img_content)
                format = img.format
                if format == "JPEG" or format == "PNG":
                    print(f"Image format: {format}, pulling")
                    img_content = BytesIO()
                    img.thumbnail((1000, 1000), Image.ANTIALIAS)
                    img.save(img_content, format=format, optimize=True, quality=75)
                    img_content.seek(0)

                    # file_name = urllib.parse.quote(Path(image_url).name)
                    if format == "JPEG":
                        file_name = "image.jpg"
                    elif format == "PNG":
                        file_name = "image.png"
                    aws_key = f"nft_image/{token.smart_contract.address}/{token.token_id}/{ts}/{file_name}"
                    client.upload_fileobj(
                        img_content, settings.AWS_STORAGE_BUCKET_NAME, aws_key
                    )
                    token.image = f"{base_path}/{aws_key}"
                    token.image_src = image_url_hash
                else:
                    print(f"Image format: {format}, skipping")
            except Exception as e:
                print(e)

    if animation_url and (
        animation_url.startswith("data:")
        or animation_url.startswith("ipfs:")
        or animation_url.startswith("http:")
        or animation_url.startswith("https:")
    ):
        if animation_url.startswith("ipfs://"):
            animation_url = (
                "https://quixotic.infura-ipfs.io/ipfs/"
                + animation_url[len("ipfs://") :]
            )
        elif animation_url.startswith("https://gateway.pinata.cloud/"):
            animation_url = animation_url.replace(
                "https://gateway.pinata.cloud/", "https://quixotic.infura-ipfs.io/"
            )
        elif animation_url.startswith("https://ipfs.infura.io/"):
            animation_url = animation_url.replace(
                "https://ipfs.infura.io/", "https://quixotic.infura-ipfs.io/"
            )
        elif animation_url.startswith("https://ipfs.io/"):
            animation_url = animation_url.replace(
                "https://ipfs.io/", "https://quixotic.infura-ipfs.io/"
            )

        animation_url_hash = hashlib.md5(animation_url.encode("utf-8")).hexdigest()
        if (
            token.animation_url_src
            and token.animation_url_src == animation_url_hash
            and token.animation_url.startswith(base_path)
        ):
            print("Animation url didn't change, so not pulling.")
            return

        if animation_url.startswith("ipfs://"):
            try:
                r = requests.get(
                    f"https://quixotic.infura-ipfs.io/ipfs/{animation_url[len('ipfs://'):]}"
                )
            except Exception:
                print(f"Invalid URL: {animation_url}")
                return
        else:
            try:
                r = requests.get(animation_url)
            except Exception:
                print(f"Invalid URL: {animation_url}")
                token.animation_url = None
                token.save()
                return

        if r.status_code >= 400:
            print(f"The request returned a bad status code {r}")
            return

        # Compress & store file if png or jpg image
        try:
            img_content = BytesIO(r.content)
            img = Image.open(img_content)
            format = img.format
            if format == "JPEG" or format == "PNG":
                img_content = BytesIO()
                img.thumbnail((1000, 1000), Image.ANTIALIAS)
                img.save(img_content, format=format, optimize=True, quality=75)
                img_content.seek(0)

                # file_name = urllib.parse.quote(Path(animation_url).name)
                if format == "JPEG":
                    file_name = "image.jpg"
                elif format == "PNG":
                    file_name = "image.png"
                aws_key = f"nft_animation/{token.smart_contract.address}/{token.token_id}/{ts}/{file_name}"
                client.upload_fileobj(
                    img_content, settings.AWS_STORAGE_BUCKET_NAME, aws_key
                )
                token.animation_url = f"{base_path}/{aws_key}"
                token.animation_url_src = animation_url_hash
        except Exception as e:
            print(e)

        # file_name = Path(animation_url).name
        # aws_key = f"nft_image/{token.smart_contract.address}/{token.token_id}/{ts}/{file_name}"
        # client.upload_fileobj(BytesIO(r.content), settings.AWS_STORAGE_BUCKET_NAME, aws_key)
        # token.animation_url = f"{base_path}/{aws_key}"
        # token.animation_url_src = animation_url_hash

    token.save()
