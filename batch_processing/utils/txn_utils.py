from api.utils.constants import w3

import json
from api.utils.Erc721Contract import Erc721Contract
from api.utils.hex_utils import HexJsonEncoder



def get_transfer_log(txn_id):
    TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    transfer_txn = w3.eth.getTransactionReceipt(txn_id)
    transfer_log = None
    for log in transfer_txn['logs']:
        if log['topics'][0].hex() == TOPIC:
            transfer_log = log
            break
    if transfer_log:
        log_dict = dict(transfer_log)
        return json.dumps(log_dict, cls=HexJsonEncoder)
    else:
        print("Transfer log not found")
        return


def get_transfer_logs(txn_id):
    TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    transfer_txn = w3.eth.getTransactionReceipt(txn_id)
    transfer_logs = []
    addr_dict = {}
    for log in transfer_txn['logs']:
        address = log['address']
        if addr_dict.get("address"):
            address_is_erc721 = True
        else:
            address_is_erc721 = Erc721Contract(address).is_erc721()
            addr_dict[address] = address_is_erc721
        if log['topics'][0].hex() == TOPIC and address_is_erc721:
            log_dict = dict(log)
            recoded_log_dict = json.loads(json.dumps(log_dict, cls=HexJsonEncoder))
            transfer_logs.append(recoded_log_dict)

    return transfer_logs


def get_transfer_log(txn_id):
    TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    transfer_txn = w3.eth.getTransactionReceipt(txn_id)
    transfer_logs = []
    for log in transfer_txn['logs']:
        if log['topics'][0].hex() == TOPIC:
            log_dict = dict(log)
            json_event = json.dumps(log_dict, cls=HexJsonEncoder)
            transfer_logs.append(json_event)
    return transfer_logs
