import os

from web3 import Web3
from web3.middleware import geth_poa_middleware

NETWORK = os.environ.get("NETWORK")
ALCHEMY_API_KEY = os.environ.get("ALCHEMY_API_KEY")
ALCHEMY_URL = f"https://{NETWORK}.g.alchemy.com/v2/{ALCHEMY_API_KEY}"
ALCHEMY_WS_URL = f"wss://{NETWORK}.g.alchemy.com/v2/{ALCHEMY_API_KEY}"
ETH_ALCHEMY_URL = f"https://eth-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}"
ETH_ALCHEMY_WS_URL = f"wss://eth-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}"
ETH_MAINNET_ALCHEMY_URL = f"https://eth-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}"


if L2_WS_ALCHEMY_API_KEY := os.environ.get("L2_WS_ALCHEMY_API_KEY"):
    ALCHEMY_WS_URL = f"wss://{NETWORK}.g.alchemy.com/v2/{L2_WS_ALCHEMY_API_KEY}"

if L1_WS_ALCHEMY_API_KEY := os.environ.get("L1_WS_ALCHEMY_API_KEY"):
    ETH_ALCHEMY_WS_URL = f"wss://eth-mainnet.g.alchemy.com/v2/{L1_WS_ALCHEMY_API_KEY}"

MARKETPLACE_FEE = 0.025
MARKETPLACE_PAYOUT_ADDRESS = "0xeC1557A67d4980C948cD473075293204F4D280fd"

SEAPORT_TRANSFER_TOPIC = (
    "0x9d9af8e38d66c62e2c12f0225249fd9d721c54b83f48d9352c97c6cacdcb6f31"
)
ERC_721_SAFE_TRANSFER_TOPIC = (
    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
)
ERC_1155_SAFE_TRANSFER_TOPIC = (
    "0xc3d58168c5ae7397731d063d5bbf3d657854427343f4c083240f7aacaa2d0f62"
)

IS_CELERY_PROCESSING_TXNS = "IS_CELERY_PROCESSING_TXNS_KEY"

if NETWORK == "opt-mainnet":
    EXCHANGE_CONTRACT_V6_ADDRESS = "0x998EF16Ea4111094EB5eE72fC2c6f4e6E8647666"
    BLUESWEEP_CONTRACT_ADDRESS = "0xbbbBbbBE843515689f3182B748B5671665541E58"
    REWARD_WRAPPER_ADDRESS = "0xC78A09D6a4badecc7614A339FD264B7290361ef1"
    CAMPAIGN_TRACKER_ADDRESS = "0x3Dadc74B465034276bE0Fa55240e1a67d7e3a266"
    L2ERC721_BRIDGE = "0x5a7749f83b81B301cAb5f48EB8516B986DAef23D"
    WEBSITE_URL = "https://qx.app"
    CHAIN_ID = 10
    NULL_PROFILE_INTERNAL_ID = 1407
    BRIDGE_PROFILE_INTERNAL_ID = 1693329

elif NETWORK == "opt-goerli":
    EXCHANGE_CONTRACT_V6_ADDRESS = "0xA943370D40d2470d45CECD9093278fd8BB830e58"
    BLUESWEEP_CONTRACT_ADDRESS = ""
    REWARD_WRAPPER_ADDRESS = ""
    CAMPAIGN_TRACKER_ADDRESS = ""
    WEBSITE_URL = "https://goerli.qx.app"
    L2ERC721_BRIDGE = "0x8DD330DdE8D9898d43b4dc840Da27A07dF91b3c9"
    ETH_ALCHEMY_URL = f"https://eth-goerli.g.alchemy.com/v2/{ALCHEMY_API_KEY}"
    ETH_ALCHEMY_WS_URL = f"wss://eth-goerli.g.alchemy.com/v2/{ALCHEMY_API_KEY}"
    CHAIN_ID = 420
    NULL_PROFILE_INTERNAL_ID = 1
    BRIDGE_PROFILE_INTERNAL_ID = 13242
else:
    EXCHANGE_CONTRACT_V6_ADDRESS = ""
    BLUESWEEP_CONTRACT_ADDRESS = ""
    REWARD_WRAPPER_ADDRESS = ""
    CAMPAIGN_TRACKER_ADDRESS = ""
    L2ERC721_BRIDGE = ""
    WEBSITE_URL = ""
    CHAIN_ID = ""
    NULL_PROFILE_INTERNAL_ID = None
    BRIDGE_PROFILE_INTERNAL_ID = None


w3 = Web3(Web3.HTTPProvider(ALCHEMY_URL))
eth_web3 = Web3(Web3.HTTPProvider(ETH_ALCHEMY_URL))
eth_mainnet_web3 = Web3(Web3.HTTPProvider(ETH_MAINNET_ALCHEMY_URL))

w3.middleware_onion.inject(geth_poa_middleware, layer=0)
