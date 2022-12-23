import re


def parse_eip681_uri(uri):
    pattern = re.compile("^ethereum:(0x[a-fA-F0-9]{40})(@[1-9]+)?\/(.*)\?(.*)=(.*)$")
    m = pattern.match(uri)
    address, chain_id, contract_method, arg_name, arg = m.groups()
    return address, chain_id[1:], contract_method, arg_name, arg
