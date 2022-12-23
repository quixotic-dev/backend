import os

from api.abis.erc721_factory_abi import erc721_factory_abi
from api.utils.constants import NETWORK, w3
from api.utils.Erc721Contract import Erc721Contract
from web3 import Web3


class Erc721Factory:
    def __init__(self):
        if NETWORK == "opt-mainnet":
            address = "0x4482B6510dF4C723Bdf80c4441dBDbc855AB29AC"
        elif NETWORK == "opt-goerli":
            address = "0x83F019dE99dB0cA483A5f2fC7053D3EA57BdE06D"

        self.contract = w3.eth.contract(address=address, abi=erc721_factory_abi)

    def deploy_contract(self, address):
        address = Web3.toChecksumAddress(address)
        network_id = "eth-" + NETWORK[4:]
        l1_contract = Erc721Contract(address, network_id)
        name = l1_contract.name()
        symbol = l1_contract.symbol()

        deployer_address = os.environ.get("BRIDGE_DEPLOYER_ADDRESS")
        deployer_private_key = os.environ.get("BRIDGE_DEPLOYER_KEY")
        nonce = w3.eth.getTransactionCount(deployer_address)

        if NETWORK == "opt-mainnet":
            transaction = self.contract.functions.createOptimismMintableERC721(
                address, name, symbol
            ).buildTransaction(
                {
                    "chainId": 10,
                    "from": deployer_address,
                    "gas": 3000000,
                    "gasPrice": w3.toWei("0.001", "gwei"),
                    "nonce": nonce,
                }
            )

        elif NETWORK == "opt-goerli":
            transaction = self.contract.functions.createOptimismMintableERC721(
                address, name, symbol
            ).buildTransaction(
                {
                    "chainId": 420,
                    "from": deployer_address,
                    "gas": 3000000,
                    "gasPrice": w3.toWei("0.001", "gwei"),
                    "nonce": nonce,
                }
            )

        signed_txn = w3.eth.account.sign_transaction(
            transaction, private_key=deployer_private_key
        )
        tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        tx = w3.eth.wait_for_transaction_receipt(tx_hash)
        return tx
