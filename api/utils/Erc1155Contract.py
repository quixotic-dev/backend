import json
from datetime import datetime, timedelta, timezone

from web3 import Web3

from ..abis.erc1155_abi import erc1155_abi
from .constants import ALCHEMY_API_KEY, NETWORK, w3


class Erc1155Contract:
    def __init__(self, contract_address, network_id: str = None):
        if network_id and network_id != NETWORK:
            self.w3 = Web3(
                Web3.HTTPProvider(
                    f"https://{network_id}.g.alchemy.com/v2/{ALCHEMY_API_KEY}"
                )
            )
        else:
            self.w3 = w3

        self.contract = self.w3.eth.contract(address=contract_address, abi=erc1155_abi)

    def name(self):
        try:
            return self.contract.functions.name().call()
        except Exception:
            return ""

    def symbol(self):
        try:
            return self.contract.functions.symbol().call()
        except Exception:
            return ""

    def balance_of(self, address: str, id: int):
        id = int(id)
        address = Web3.toChecksumAddress(address)
        try:
            return self.contract.functions.balanceOf(address, id).call()
        except Exception:
            return 0

    def total_supply(self, last_supply_pull):
        try:
            supply = self.contract.functions.totalSupply().call()
        except Exception:
            cooldown_int = 12
            cooldown = timedelta(hours=cooldown_int)
            if last_supply_pull and last_supply_pull + cooldown > datetime.now(
                tz=timezone.utc
            ):
                return print(
                    f"You can only manually query total supply once every {cooldown_int} hours"
                )
            single_events = self.single_transfer_events_from_address(
                address="0x0000000000000000000000000000000000000000"
            )
            batch_events = self.batch_transfer_events_from_address(
                address="0x0000000000000000000000000000000000000000"
            )
            events = single_events + batch_events
            tokens = set()
            for event in events:
                tokens.add(event["args"]["id"])
            supply = len(tokens)
        return supply

    def contract_uri(self):
        try:
            return self.contract.functions.contractURI().call()
        except Exception:
            return None

    def token_uri(self, i):
        i = int(i)
        return self.contract.functions.uri(i).call()

    def owner(self):
        return self.contract.functions.owner().call()

    def fetch_single_events(self, from_block, to_block, address=None, token=None):
        print(f"Fetching single transfer events from {from_block} to {to_block}")
        if address is not None:
            filter = self.contract.events.TransferSingle.createFilter(
                fromBlock=from_block,
                toBlock=to_block,
                argument_filters={"from": address},
            )
        elif token is not None:
            filter = self.contract.events.TransferSingle.createFilter(
                fromBlock=from_block, toBlock=to_block, argument_filters={"id": token}
            )
        else:
            filter = self.contract.events.TransferSingle.createFilter(
                fromBlock=from_block, toBlock=to_block
            )
        events = filter.get_all_entries()
        return events

    def fetch_batch_events(self, from_block, to_block, address=None):
        print(f"Fetching batch transfer events from {from_block} to {to_block}")
        if address is not None:
            filter = self.contract.events.TransferBatch.createFilter(
                fromBlock=from_block,
                toBlock=to_block,
                argument_filters={"from": address},
            )
        else:
            filter = self.contract.events.TransferBatch.createFilter(
                fromBlock=from_block, toBlock=to_block
            )
        events = filter.get_all_entries()
        return events

    def single_transfer_events(self, last_block_checked="0x1"):
        try:
            events = self.fetch_single_events(
                from_block=last_block_checked, to_block="latest"
            )
        except Exception as e:
            e = json.loads(str(e).replace("'", '"'))
            from_block = last_block_checked
            to_block = e["message"].split("[")[1].split(",")[1][:-1].strip()
            latest_block = hex(self.w3.eth.block_number)
            events = []
            while int(to_block, 16) < int(latest_block, 16):
                events += self.fetch_single_events(
                    from_block=from_block, to_block=to_block
                )
                from_block = to_block
                try:
                    events += self.fetch_single_events(
                        from_block=from_block, to_block="latest"
                    )
                    to_block = latest_block
                except Exception as e:
                    e = json.loads(str(e).replace("'", '"'))
                    to_block = e["message"].split("[")[1].split(",")[1][:-1].strip()
        return events

    def single_transfer_events_from_address(self, address, last_block_checked="0x1"):
        address = Web3.toChecksumAddress(address)
        try:
            events = self.fetch_single_events(
                from_block=last_block_checked, to_block="latest", address=address
            )
        except Exception as e:
            e = json.loads(str(e).replace("'", '"'))
            from_block = last_block_checked
            to_block = e["message"].split("[")[1].split(",")[1][:-1].strip()
            latest_block = hex(self.w3.eth.block_number)
            events = []

            # Very ugly fix for when Alchemy API can't return results due to 10k tx's in 1 block
            if int(to_block, 16) <= int(from_block, 16):
                return []

            while int(to_block, 16) < int(latest_block, 16):
                events += self.fetch_single_events(
                    from_block=from_block, to_block=to_block, address=address
                )
                from_block = to_block
                try:
                    events += self.fetch_single_events(
                        from_block=from_block, to_block="latest", address=address
                    )
                    to_block = latest_block
                except Exception as e:
                    e = json.loads(str(e).replace("'", '"'))
                    to_block = e["message"].split("[")[1].split(",")[1][:-1].strip()

                    # Very ugly fix for when Alchemy API can't return results due to 10k tx's in 1 block
                    if int(to_block, 16) <= int(from_block, 16):
                        return []
        return events

    def single_transfer_events_for_token(self, i, last_block_checked="0x1"):
        i = int(i)
        try:
            events = self.fetch_single_events(
                from_block=last_block_checked, to_block="latest", token=i
            )
        except Exception as e:
            e = json.loads(str(e).replace("'", '"'))
            from_block = last_block_checked
            to_block = e["message"].split("[")[1].split(",")[1][:-1].strip()
            latest_block = hex(self.w3.eth.block_number)
            events = []
            while int(to_block, 16) < int(latest_block, 16):
                events += self.fetch_single_events(
                    from_block=from_block, to_block=to_block, token=i
                )
                from_block = to_block
                try:
                    events += self.fetch_single_events(
                        from_block=from_block, to_block="latest", token=i
                    )
                    to_block = latest_block
                except Exception as e:
                    e = json.loads(str(e).replace("'", '"'))
                    to_block = e["message"].split("[")[1].split(",")[1][:-1].strip()
        return events

    def batch_transfer_events(self, last_block_checked="0x1"):
        try:
            events = self.fetch_batch_events(
                from_block=last_block_checked, to_block="latest"
            )
        except Exception as e:
            e = json.loads(str(e).replace("'", '"'))
            from_block = last_block_checked
            to_block = e["message"].split("[")[1].split(",")[1][:-1].strip()
            latest_block = hex(self.w3.eth.block_number)
            events = []
            while int(to_block, 16) < int(latest_block, 16):
                events += self.fetch_batch_events(
                    from_block=from_block, to_block=to_block
                )
                from_block = to_block
                try:
                    events += self.fetch_batch_events(
                        from_block=from_block, to_block="latest"
                    )
                    to_block = latest_block
                except Exception as e:
                    e = json.loads(str(e).replace("'", '"'))
                    to_block = e["message"].split("[")[1].split(",")[1][:-1].strip()

        single_events = []

        for event in events:
            for index, token in enumerate(event["args"]["ids"]):
                new_event = {
                    "args": {
                        "from": event["args"]["from"],
                        "to": event["args"]["to"],
                        "id": token,
                        "value": event["args"]["values"][index],
                    },
                    "transactionHash": event["transactionHash"],
                    "address": event["address"],
                }
                single_events.append(new_event)
        return single_events

    def batch_transfer_events_from_address(self, address, last_block_checked="0x1"):
        address = Web3.toChecksumAddress(address)
        try:
            events = self.fetch_batch_events(
                from_block=last_block_checked, to_block="latest", address=address
            )
        except Exception as e:
            e = json.loads(str(e).replace("'", '"'))
            from_block = last_block_checked
            to_block = e["message"].split("[")[1].split(",")[1][:-1].strip()
            latest_block = hex(self.w3.eth.block_number)
            events = []
            while int(to_block, 16) < int(latest_block, 16):
                events += self.fetch_batch_events(
                    from_block=from_block, to_block=to_block, address=address
                )
                from_block = to_block
                try:
                    events += self.fetch_batch_events(
                        from_block=from_block, to_block="latest", address=address
                    )
                    to_block = latest_block
                except Exception as e:
                    e = json.loads(str(e).replace("'", '"'))
                    to_block = e["message"].split("[")[1].split(",")[1][:-1].strip()

        single_events = []

        for event in events:
            for index, token in enumerate(event["args"]["ids"]):
                new_event = {
                    "args": {
                        "from": event["args"]["from"],
                        "to": event["args"]["to"],
                        "id": token,
                        "value": event["args"]["values"][index],
                    },
                    "transactionHash": event["transactionHash"],
                    "address": event["address"],
                }
                single_events.append(new_event)
        return single_events

    def batch_transfer_events_for_token(self, i, last_block_checked="0x1"):
        i = int(i)
        try:
            events = self.fetch_batch_events(
                from_block=last_block_checked, to_block="latest"
            )
        except Exception as e:
            e = json.loads(str(e).replace("'", '"'))
            from_block = last_block_checked
            to_block = e["message"].split("[")[1].split(",")[1][:-1].strip()
            latest_block = hex(self.w3.eth.block_number)
            events = []
            while int(to_block, 16) < int(latest_block, 16):
                events += self.fetch_batch_events(
                    from_block=from_block, to_block=to_block
                )
                from_block = to_block
                try:
                    events += self.fetch_batch_events(
                        from_block=from_block, to_block="latest"
                    )
                    to_block = latest_block
                except Exception as e:
                    e = json.loads(str(e).replace("'", '"'))
                    to_block = e["message"].split("[")[1].split(",")[1][:-1].strip()

        events_with_token = []
        for event in events:
            try:
                index = event["args"]["ids"].index(i)
                new_event = {
                    "args": {
                        "from": event["args"]["from"],
                        "to": event["args"]["to"],
                        "id": i,
                        "value": event["args"]["values"][index],
                    },
                    "transactionHash": event["transactionHash"],
                    "address": event["address"],
                }
                events_with_token.append(new_event)
            except Exception as e:
                pass
        return events_with_token
