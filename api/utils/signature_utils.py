from datetime import datetime, timedelta

from .recover_address import recover_address


def timestamp_is_fresh(message):
    """
    The message must have been signed in the past hour.
    """
    timestamp = int(message[-13:]) / 1000
    return datetime.fromtimestamp(timestamp) < datetime.now() + timedelta(minutes=15)


def verify_profile_signature(message, signature, address):
    message_beginning = """Sign this message to update your settings. It won't cost you any Ether. Timestamp:"""
    if not timestamp_is_fresh(message) or not message_beginning.startswith(message_beginning):
        raise Exception(
            f"Received a stale timestamp on a signed message. Flagging because this is suspicious: {message}, {signature}, {address}"
        )

    if not recover_address(message, signature) == address:
        raise Exception(
            f"Received bad signature: Flagging because this is suspicious: {repr(message)}, {signature}, {address}"
        )
    return recover_address(message, signature) == address


def verify_collection_signature(message, signature, address):
    assert type(address) is str, "Address must be a string"

    message_beginning = """Sign this message to update your the settings on your collection. It won't cost you any Ether. Timestamp:"""
    if not timestamp_is_fresh(message) or not message_beginning.startswith(message_beginning):
        return False

    print("recovered address")
    recovered_address = recover_address(message, signature)
    print(recovered_address, type(recovered_address))
    print("expected address")
    print(address, type(address))
    print("do they match?")
    print(recovered_address == address)
    return recover_address(message, signature) == address