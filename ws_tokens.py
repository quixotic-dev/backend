import asyncio
import json
import subprocess

import websockets
from websockets import exceptions

from api.utils.constants import ALCHEMY_WS_URL


# Listen for transfer events from known ERC721/1155 collections
async def start_websocket(collection_ids_subset):
    print(f"Initializing tokens websocket")
    async with websockets.connect(ALCHEMY_WS_URL) as websocket:
        for col_id, col_type in collection_ids_subset:
            if col_type == "721":
                safe_transfer_from_topic = (
                    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
                )
                req = f'{{"jsonrpc":"2.0","id": 1, "method": "eth_subscribe", "params": ["logs", {{"address": "{col_id}", "topics": ["{safe_transfer_from_topic}"]}}]}}'
                print(req)
                await websocket.send(req)

            elif col_type == "1155":
                safe_transfer_from_topic = (
                    "0xc3d58168c5ae7397731d063d5bbf3d657854427343f4c083240f7aacaa2d0f62"
                )
                req1 = f'{{"jsonrpc":"2.0","id": 1, "method": "eth_subscribe", "params": ["logs", {{"address": "{col_id}", "topics": ["{safe_transfer_from_topic}"]}}]}}'
                print(req1)
                await websocket.send(req1)

                batch_transfer_topic = (
                    "0x4a39dc06d4c0dbc64b70af90fd698a233a518aa5d07e595d983b8c0526c8f7fb"
                )
                req2 = f'{{"jsonrpc":"2.0","id": 1, "method": "eth_subscribe", "params": ["logs", {{"address": "{col_id}", "topics": ["{batch_transfer_topic}"]}}]}}'
                print(req2)
                await websocket.send(req2)

        async for message_str in websocket:
            print(f"New WS message: {message_str}")
            try:
                message = json.loads(message_str)
                params = message.get("params")
                if params:
                    transfer_event = params["result"]
                    subprocess.Popen(
                        [
                            "python",
                            "manage.py",
                            "process_transfer_txn",
                            json.dumps(transfer_event),
                        ]
                    )
            except Exception as e:
                print(e)


async def create_websockets():
    p = subprocess.run(
        ["python", "manage.py", "get_approved_contracts"],
        capture_output=True,
        text=True,
    )
    collection_ids = json.loads(p.stdout)

    chunkSize = 500
    i = 0
    print(f"There are {len(collection_ids)} contracts")
    websockets = []
    while i < len(collection_ids):
        collection_ids_subset = collection_ids[i : i + chunkSize]
        print(f"Creating websocket for contracts indexed {i} through {i+chunkSize-1}")
        websockets.append(start_websocket(collection_ids_subset))
        i += chunkSize
    await asyncio.gather(*websockets)


try:
    asyncio.run(create_websockets())
except (exceptions.ConnectionClosedError, asyncio.exceptions.IncompleteReadError) as e:
    print(e)
    asyncio.run(create_websockets())
