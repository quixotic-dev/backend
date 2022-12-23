from django.http import HttpResponse
from django.core.cache import cache
from api.utils.constants import IS_CELERY_PROCESSING_TXNS
import logging

def heath_view(request):
    logging.warning("Running Health Check")
    return HttpResponse(status=200)

def default_view(request):
    logging.warning("Visited Root URL. There's nothing here.")
    return HttpResponse(status=200)

def error_view(request):
    raise Exception("You have triggered an error")
    return HttpResponse(status=200)

def celery_health(request):
    if cache.get(IS_CELERY_PROCESSING_TXNS):
        return HttpResponse(status=200)
    else:
        return HttpResponse(status=500)
