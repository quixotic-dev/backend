from django.core.mail import send_mail
from django.conf import settings
from api.utils.constants import NETWORK, WEBSITE_URL


def send_email_about_contract(collection):
    if NETWORK.split("-")[1] == "mainnet":
        try:
            frontend_url = f"{WEBSITE_URL}/collection/{collection.address}"
            backend_url = f"https://quixotic-{NETWORK}-develop.herokuapp.com/admin/api/erc721collection/{collection.id}/change/"
            emails = [e[1] for e in settings.ADMINS]
            send_mail(
                subject=f"Contract added to {NETWORK}: {collection.name if collection.name else collection.address}",
                message=None,
                html_message=f'A new contract was added: <a href="{frontend_url}">frontend</a>, <a href="{backend_url}">backend</a>.',
                from_email="alerts@dev.quixotic.io",
                recipient_list=emails,
            )
        except Exception as e:
            print(e)


def send_email_about_signatures(order_dict, order_hash):
    emails = [e[1] for e in settings.ADMINS]
    send_mail(
        subject=f"Failed Signature Validation",
        message=f"Order: {order_dict}\nOrder Hash: {order_hash}",
        from_email="alerts@dev.quixotic.io",
        recipient_list=emails,
    )


def send_email_about_campaign_budget(campaign):
    emails = [e[1] for e in settings.ADMINS]
    backend_url = f"https://quixotic-opt-mainnet-develop.herokuapp.com/bBBzitCP/api/rewardscampaign/{campaign.id}/change/"
    emails = [e[1] for e in settings.ADMINS]
    send_mail(
        subject=f"{campaign.collection.name} campaign budget has {str(int(campaign.budget - campaign.distributed))} OP remaining",
        message=None,
        html_message=f'<a href="{backend_url}">View rewards campaign for {campaign.collection.name}</a>',
        from_email="campaigns@dev.quixotic.io",
        recipient_list=emails,
    )


def send_email_about_campaign_distribution(campaign):
    emails = [e[1] for e in settings.ADMINS]
    backend_url = f"https://quixotic-opt-mainnet-develop.herokuapp.com/bBBzitCP/api/rewardscampaign/{campaign.id}/change/"
    emails = [e[1] for e in settings.ADMINS]
    send_mail(
        subject=f"{campaign.collection.name} rewards distribution has spiked by 250+ OP in the last 10 minutes",
        message=None,
        html_message=f'<a href="{backend_url}">View rewards campaign for {campaign.collection.name}</a>',
        from_email="campaigns@dev.quixotic.io",
        recipient_list=emails,
    )
