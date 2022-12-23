from api.models import (
    CollectionType,
    Contract,
    Erc721Collection,
    Network,
    NonNFTContract,
)
from api.utils.constants import NETWORK
from api.utils.email_utils import send_email_about_contract
from api.utils.Erc165Contract import Erc165Contract
from web3 import Web3


def get_or_create_contract(
    address, approved_only=False, save_non_nft_contract=False, network=NETWORK
):
    try:
        address = Web3.toChecksumAddress(address)
        network = Network.objects.get(network_id=network)
    except Exception as e:
        print(e)
        return None

    try:
        smart_contract = Contract.objects.get(address=address, network=network)
        if smart_contract.collection.approved or not approved_only:
            return smart_contract
        else:
            return None
    except Contract.DoesNotExist as e:
        print(e)
        try:
            NonNFTContract.objects.get(address=address, network=network)
            return None
        except NonNFTContract.DoesNotExist as e:
            print(e)
            try:
                contract = Erc165Contract(address, network_id=network.network_id)
            except Exception as e:
                print(e)
                return None

            if contract.supports_721_interface():
                smart_contract = Contract.objects.create(
                    address=address, approved=True, network=network
                )
                collection = Erc721Collection.objects.create(
                    address=address,
                    primary_contract=smart_contract,
                    approved=True,
                    network=network,
                )
                smart_contract.collection = collection
                smart_contract.save()
                smart_contract.refresh_contract()
                collection.refresh_collection()
                collection.refresh_metadata()
                send_email_about_contract(collection)
                return smart_contract
            elif contract.supports_1155_interface():
                smart_contract = Contract.objects.create(
                    address=address,
                    type=CollectionType.ERC1155,
                    approved=True,
                    network=network,
                )
                collection = Erc721Collection.objects.create(
                    address=address,
                    type=CollectionType.ERC1155,
                    primary_contract=smart_contract,
                    approved=True,
                    network=network,
                )
                smart_contract.collection = collection
                smart_contract.save()
                smart_contract.refresh_contract()
                collection.refresh_collection()
                collection.refresh_metadata()
                send_email_about_contract(collection)
                return smart_contract
            else:
                if save_non_nft_contract:
                    NonNFTContract.objects.get_or_create(
                        address=address, network=network
                    )
                return None
