import asyncio
import base64
import json
import os
import subprocess
from asyncio import exceptions
from time import sleep

import discord
import requests
import websockets
from web3 import Web3

from api.utils.Erc1155Contract import Erc1155Contract
from api.utils.Erc721Contract import Erc721Contract
from api.utils.ExchangeContract import exchange_addresses
from api.utils.constants import ALCHEMY_WS_URL, WEBSITE_URL, w3

ERC_721_SAFE_TRANSFER_TOPIC = (
    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
)
ERC_1155_SAFE_TRANSFER_TOPIC = (
    "0xc3d58168c5ae7397731d063d5bbf3d657854427343f4c083240f7aacaa2d0f62"
)
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL = os.getenv("DISCORD_CHANNEL")

client = discord.Client()


@client.event
async def on_ready():
    print("Connected to Discord")
    await alchemy_websocket()


@client.event
async def on_error(self):
    print("Caught discord error")


def pull_metadata(contract, token_id):
    try:
        metadata_uri = contract.token_uri(token_id)
    except exceptions.ContractLogicError as e:
        return

    if not metadata_uri:
        return

    ipfs_prefix = "ipfs://"
    if metadata_uri.startswith(ipfs_prefix):
        try:
            r = requests.get(
                f"https://quixotic.infura-ipfs.io/ipfs/{metadata_uri[len(ipfs_prefix):]}"
            )
            metadata_str = r.text
            metadata = json.loads(metadata_str)
        except json.JSONDecodeError:
            metadata = {}
    elif metadata_uri.startswith("data:application/json;base64"):
        prefix, msg = metadata_uri.split(",")
        metadata = json.loads(base64.b64decode(msg))
    else:
        try:
            r = requests.get(metadata_uri)
            metadata = json.loads(r.text)
        except Exception:
            return None

    return metadata


async def send_discord_message(transfer_event):
    transfer_txn_id = transfer_event["transactionHash"]
    # print(f"Processing transfer event {transfer_txn_id}")
    full_txn = w3.eth.get_transaction(transfer_txn_id)
    if not full_txn["to"] in exchange_addresses:
        return

    amount = Web3.fromWei(full_txn["value"], "ether")

    if amount < 0.005:
        return

    amount = str(amount) + " ETH"

    contract_address = Web3.toChecksumAddress(transfer_event["address"])
    func_hash, *other_topics = transfer_event["topics"]

    if func_hash == ERC_721_SAFE_TRANSFER_TOPIC:
        contract = Erc721Contract(contract_address)
        from_bytes, to_bytes, token_id_bytes = other_topics
        # from_address = to_checksum_address_from_bytes(from_bytes)
        # to_address = to_checksum_address_from_bytes(to_bytes)
        token_id = int(token_id_bytes, 16)
        quantity = 1
    elif func_hash == ERC_1155_SAFE_TRANSFER_TOPIC:
        contract = Erc1155Contract(contract_address)
        # operator_addr, from_address, to_address = (to_checksum_address_from_bytes(t) for t in other_topics)
        token_id, quantity = int(transfer_event["data"][:66], 16), int(
            transfer_event["data"][66:], 16
        )

    metadata = pull_metadata(contract, token_id)
    if not metadata:
        print(f"Could not pull metadata")
        return

    name = metadata.get("name")
    if not name:
        try:
            contract_name = contract.name()
            name = f"{contract_name} #{token_id}"
        except Exception:
            print(f"Name missing from metadata")
            return

    url = f"{WEBSITE_URL}/asset/{contract_address}/{token_id}"
    message = f"{name} sold for {amount}: {url}"

    channel = client.get_channel(int(CHANNEL))
    await channel.send(message)


async def alchemy_websocket():
    p = subprocess.run(
        ["python", "manage.py", "get_discord_collections"],
        capture_output=True,
        text=True,
    )
    collection_ids = json.loads(p.stdout)
    print(f"Initializing alchemy websocket.")
    async with websockets.connect(ALCHEMY_WS_URL) as websocket:
        for col_id, col_type in collection_ids:
            if col_type == "721":
                safe_transfer_from_topic = (
                    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
                )
                req = f'{{"jsonrpc":"2.0","id": 1, "method": "eth_subscribe", "params": ["logs", {{"address": "{col_id}", "topics": ["{safe_transfer_from_topic}"]}}]}}'
            elif col_type == "1155":
                safe_transfer_from_topic = (
                    "0xc3d58168c5ae7397731d063d5bbf3d657854427343f4c083240f7aacaa2d0f62"
                )
                req = f'{{"jsonrpc":"2.0","id": 1, "method": "eth_subscribe", "params": ["logs", {{"address": "{col_id}", "topics": ["{safe_transfer_from_topic}"]}}]}}'
            else:
                print(f"Unrecognized col_type: {col_type}")
            print(req)
            await websocket.send(req)

        async for message_str in websocket:
            print(f"New WS message: {message_str}")
            message = json.loads(message_str)
            params = message.get("params")
            if params:
                transfer_event = params["result"]
                asyncio.create_task(send_discord_message(transfer_event))


def start_websocket():
    try:
        asyncio.run(client.run(TOKEN, reconnect=True))
    except Exception as e:
        print(e)
        sleep(1)
        start_websocket()


start_websocket()
