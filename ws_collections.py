import asyncio
import json
import subprocess

import websockets

from api.utils.constants import ALCHEMY_WS_URL


# Listen for new contract deployments
async def start_websocket():
    print(f"Initializing collections websocket")
    async with websockets.connect(ALCHEMY_WS_URL) as websocket:
        topic_one = "0x8be0079c531659141344cd1fd0a4f28419497f9722a3daafe3b4186f6b6457e0"
        topic_two = "0x0000000000000000000000000000000000000000000000000000000000000000"
        req = f'{{"jsonrpc":"2.0","id": 1, "method": "eth_subscribe", "params": ["logs", {{"topics": ["{topic_one}", "{topic_two}"]}}]}}'
        print(req)
        await websocket.send(req)

        async for message_str in websocket:
            print(f"New WS message: {message_str}")
            try:
                message = json.loads(message_str)
                params = message.get("params")
                if params:
                    event = params["result"]
                    subprocess.Popen(
                        [
                            "python",
                            "manage.py",
                            "process_new_contract",
                            json.dumps(event),
                        ]
                    )
            except Exception as e:
                print(e)


try:
    asyncio.run(start_websocket())
except Exception as e:
    print(e)
    asyncio.run(start_websocket())
