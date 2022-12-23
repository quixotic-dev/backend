import time

timestamp_buffer = 60


def create_timestamps(duration):
    unix_timestamp_start = int(time.time()) - timestamp_buffer
    unix_timestamp_end = unix_timestamp_start + int(duration)
    return unix_timestamp_start, unix_timestamp_end