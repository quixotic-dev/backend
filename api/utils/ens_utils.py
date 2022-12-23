from .constants import eth_mainnet_web3

from ens import ENS

ns = ENS.fromWeb3(eth_mainnet_web3)


def get_ens_for_address(address):
    try:
        domain = ns.name(address)
        if ns.address(domain) == address:
            return domain
        else:
            return None
    except Exception as e:
        print(e)
        return None


def get_address_for_ens(ens):
    address = ns.address(ens)
    return address
