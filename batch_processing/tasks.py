from celery import shared_task
from api.models import Erc721Token

@shared_task
def refresh_token(internal_id):
    """
    Use internal id not token id
    """
    token = Erc721Token.objects.get(id=internal_id)
    token.refresh_token()
    return True
