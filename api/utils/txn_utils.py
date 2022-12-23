from .constants import w3, ERC_721_SAFE_TRANSFER_TOPIC, ERC_1155_SAFE_TRANSFER_TOPIC
from .hex_utils import HexJsonEncoder
import json

def get_transfer_events_from_txn_id(txn_id):
    receipts = w3.eth.get_transaction_receipt(txn_id)
    logs = receipts['logs']
    transfer_logs = []
    for log in logs:
        log = json.loads(json.dumps(dict(log), cls=HexJsonEncoder))
        topic = log['topics'][0]
        if topic == ERC_721_SAFE_TRANSFER_TOPIC or topic == ERC_1155_SAFE_TRANSFER_TOPIC:
            transfer_logs.append(log)
    return transfer_logs
