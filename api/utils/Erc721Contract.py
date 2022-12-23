import json
from datetime import datetime, timedelta, timezone
from time import sleep

from web3 import Web3
from web3.exceptions import ContractLogicError

from ..abis.erc721_abi import erc721_abi
from .constants import ALCHEMY_API_KEY, NETWORK, w3


class Erc721Contract:
    def __init__(self, contract_address, network_id: str = None):
        if network_id and network_id != NETWORK:
            self.w3 = Web3(
                Web3.HTTPProvider(
                    f"https://{network_id}.g.alchemy.com/v2/{ALCHEMY_API_KEY}"
                )
            )
        else:
            self.w3 = w3

        self.contract_address = contract_address
        self.contract = self.w3.eth.contract(address=contract_address, abi=erc721_abi)

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

    def royalty_info(self):
        try:
            return self.contract.functions.royaltyInfo(1, 100).call()
        except Exception:
            return None

    def balance_of(self, address: str):
        address = Web3.toChecksumAddress(address)
        return self.contract.functions.balanceOf(address).call()

    def token_of_owner_by_index(self, address, i, retries=3):
        try:
            i = int(i)
            address = Web3.toChecksumAddress(address)
            return self.contract.functions.tokenOfOwnerByIndex(address, i).call()
        except ValueError as e:
            if retries > 0:
                return self.token_of_owner_by_index(address, i, retries - 1)
            else:
                raise e

    def total_supply(self, last_supply_pull):
        try:
            supply = self.contract.functions.totalSupply().call()
        except Exception:
            cooldown_int = 12
            cooldown = timedelta(hours=cooldown_int)
            if last_supply_pull and last_supply_pull + cooldown > datetime.now(
                tz=timezone.utc
            ):
                print(
                    f"You can only manually query total supply once every {cooldown_int} hours"
                )
                return None
            events = self.transfer_events_from_address(
                address="0x0000000000000000000000000000000000000000"
            )
            tokens = set()
            for event in events:
                tokens.add(event["args"]["tokenId"])
            supply = len(tokens)
        return supply

    def totalSupply(self):
        try:
            supply = self.contract.functions.totalSupply().call()
            return supply
        except Exception:
            return None

    def token_by_index(self, i):
        return self.contract.functions.tokenByIndex(i).call()

    def contract_uri(self):
        try:
            return self.contract.functions.contractURI().call()
        except Exception:
            return None

    def token_uri(self, i):
        i = int(i)
        try:
            return self.contract.functions.tokenURI(i).call()
        except Exception:
            return None

    def tokenURI(self, i):
        return self.token_uri(i)

    def base_uri(self):
        try:
            return self.contract.functions.baseURI().call()
        except Exception as e:
            print(e)
            return None

    def owner_of(self, i):
        i = int(i)
        try:
            return self.contract.functions.ownerOf(i).call()
        except Exception as e:
            # if (str(e) == "execution reverted: ERC721: owner query for nonexistent token"):
            #     return "0x0000000000000000000000000000000000000000"
            # elif (str(e) == "execution reverted: ERC721A: unable to determine the owner of token"):
            #     return "0x0000000000000000000000000000000000000000"

            try:
                sleep(1)
                return self.contract.functions.ownerOf(i).call()
            except Exception:
                print(e)
                print("Error calling contract ownerOf function")
                return None

    def owner(self):
        return self.contract.functions.owner().call()

    def fetch_single_events(self, from_block, to_block, address=None, token=None):
        print(f"Fetching single transfer events from {from_block} to {to_block}")
        if address is not None:
            filter = self.contract.events.Transfer.createFilter(
                fromBlock=from_block,
                toBlock=to_block,
                argument_filters={"from": address},
            )
        elif token is not None:
            filter = self.contract.events.Transfer.createFilter(
                fromBlock=from_block,
                toBlock=to_block,
                argument_filters={"tokenId": token},
            )
        else:
            filter = self.contract.events.Transfer.createFilter(
                fromBlock=from_block, toBlock=to_block
            )
        events = filter.get_all_entries()
        return events

    def transfer_events_from_address(self, address):
        address = Web3.toChecksumAddress(address)
        try:
            events = self.fetch_single_events(
                from_block="0x1", to_block="latest", address=address
            )
        except Exception as e:
            print(e)

            try:
                e = json.loads(str(e).replace("'", '"'))
                if (
                    self.contract_address
                    == "0xfA14e1157F35E1dAD95dC3F822A9d18c40e360E2"
                ):
                    from_block = "0x2CB1276"
                    to_block = "0x2CB1278"
                    # latest_block = "0x2996B76"
                else:
                    from_block = "0x1"
                    to_block = e["message"].split("[")[1].split(",")[1][:-1].strip()
                latest_block = hex(self.w3.eth.block_number)
                events = []
            except Exception as e:
                print(e)
                return []

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
                    print(e)
                    e = json.loads(str(e).replace("'", '"'))
                    to_block = e["message"].split("[")[1].split(",")[1][:-1].strip()

                    # Very ugly fix for when Alchemy API can't return results due to 10k tx's in 1 block
                    if int(to_block, 16) <= int(from_block, 16):
                        return []
        return events

    def transfer_events_for_token(self, token):
        token = int(token)
        try:
            events = self.fetch_single_events(
                from_block="0x1", to_block="latest", token=token
            )
        except Exception as e:
            print(e)

            try:
                e = json.loads(str(e).replace("'", '"'))
                from_block = "0x1"
                to_block = e["message"].split("[")[1].split(",")[1][:-1].strip()
                latest_block = hex(self.w3.eth.block_number)
                events = []

                while int(to_block, 16) < int(latest_block, 16):
                    events += self.fetch_single_events(
                        from_block=from_block, to_block=to_block, token=token
                    )
                    from_block = to_block
                    try:
                        events += self.fetch_single_events(
                            from_block=from_block, to_block="latest", token=token
                        )
                        to_block = latest_block
                    except Exception as e:
                        e = json.loads(str(e).replace("'", '"'))
                        to_block = e["message"].split("[")[1].split(",")[1][:-1].strip()
            except Exception as e:
                print(e)
                return []
        return events

    def is_erc721(self):
        try:
            return self.contract.functions.supportsInterface("0x80ac58cd").call()
        except ContractLogicError:
            return False

    def is_approved_for_all(self, owner, operator):
        try:
            return self.contract.functions.isApprovedForAll(owner, operator).call()
        except ContractLogicError:
            return False
