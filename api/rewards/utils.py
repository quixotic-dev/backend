from api.abis.campaign_tracker_abi import campaign_tracker_abi
from api.abis.reward_wrapper_abi import reward_wrapper_abi
from api.utils.constants import CAMPAIGN_TRACKER_ADDRESS, REWARD_WRAPPER_ADDRESS, w3
from django.core.cache import cache


def get_collection_boost_id(collection_address):
    return f"COLLECTION_BOOST_{collection_address.lower()}"


def get_amount_distributed_by_campaign(campaign_str):
    cache_key = f"get_amount_distributed_by_campaign{campaign_str}"
    if res := cache.get(cache_key):
        return res

    reward_wrapper_contract = w3.eth.contract(
        address=REWARD_WRAPPER_ADDRESS, abi=reward_wrapper_abi
    )
    amount_distributed = reward_wrapper_contract.functions.getRewardSentByCampaignInOP(
        campaign_str
    ).call()
    cache.set(cache_key, amount_distributed, 5)  # Cache for 5 seconds
    return amount_distributed


def get_campaign_info(campaign_str):
    """
    Campaign Info has the following values
    campaign_str, reward_per_mille, manager, royalty_addr, royalty_per_mille, max_allowance, is_active = campaign_info
    """
    cache_key = f"get_campaign_info_{campaign_str}"
    if res := cache.get(cache_key):
        return res

    campaign_tracker_contract = w3.eth.contract(
        address=CAMPAIGN_TRACKER_ADDRESS, abi=campaign_tracker_abi
    )
    campaign_info = campaign_tracker_contract.functions.getCampaign(campaign_str).call()
    cache.set(cache_key, campaign_info, 5)  # Cache for 5 seconds
    return campaign_info


def get_amount_distributed(collection_address):
    """
    Returns unit in whole OP; Not wei-style OP
    """
    return get_amount_distributed_by_campaign(
        get_collection_boost_id(collection_address)
    ) / (10**18)


def is_eligible_for_boost(collection_address):
    campaign_info = get_campaign_info(get_collection_boost_id(collection_address))
    return bool(campaign_info[1])


def get_boost_per_mille(collection_address):
    campaign_info = get_campaign_info(get_collection_boost_id(collection_address))
    _, reward_per_mille, _, _, _, _, _ = campaign_info
    return reward_per_mille


def get_budget(collection_address):
    campaign_info = get_campaign_info(get_collection_boost_id(collection_address))
    _, _, _, _, _, max_allowance, _ = campaign_info
    return max_allowance / (10**18)


def is_campaign_active(collection_address):
    campaign_info = get_campaign_info(get_collection_boost_id(collection_address))
    _, _, _, _, _, _, is_active = campaign_info
    return is_active
