import asyncio
import json
import subprocess

import websockets
from web3 import Web3

from api.utils.constants import ALCHEMY_WS_URL


# Listen for all transfer events
async def start_websocket():
    p = subprocess.run(
        ["python3", "manage.py", "get_nft_contracts"], capture_output=True, text=True
    )
    nft_contracts = set(json.loads(p.stdout))
    p = subprocess.run(
        ["python3", "manage.py", "get_non_nft_contracts"],
        capture_output=True,
        text=True,
    )
    non_nft_contracts = set(json.loads(p.stdout))

    print(f"Initializing tokens_all websocket")
    async with websockets.connect(ALCHEMY_WS_URL) as websocket:
        safe_transfer_from_topic = (
            "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
        )
        req = f'{{"jsonrpc":"2.0","id": 1, "method": "eth_subscribe", "params": ["logs", {{"topics": ["{safe_transfer_from_topic}"]}}]}}'
        print(req)
        await websocket.send(req)

        safe_transfer_from_topic = (
            "0xc3d58168c5ae7397731d063d5bbf3d657854427343f4c083240f7aacaa2d0f62"
        )
        req1 = f'{{"jsonrpc":"2.0","id": 1, "method": "eth_subscribe", "params": ["logs", {{"topics": ["{safe_transfer_from_topic}"]}}]}}'
        print(req1)
        await websocket.send(req1)

        batch_transfer_topic = (
            "0x4a39dc06d4c0dbc64b70af90fd698a233a518aa5d07e595d983b8c0526c8f7fb"
        )
        req2 = f'{{"jsonrpc":"2.0","id": 1, "method": "eth_subscribe", "params": ["logs", {{"topics": ["{batch_transfer_topic}"]}}]}}'
        print(req2)
        await websocket.send(req2)

        async for message_str in websocket:
            print(f"New WS message: {message_str}")
            try:
                message = json.loads(message_str)
                params = message.get("params")
                if params:
                    transfer_event = params["result"]
                    contract_address = Web3.toChecksumAddress(transfer_event["address"])
                    if (
                        contract_address not in nft_contracts
                        and contract_address not in non_nft_contracts
                    ):
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


try:
    asyncio.run(start_websocket())
except Exception as e:
    print(e)
    asyncio.run(start_websocket())
