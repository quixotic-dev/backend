from functools import wraps
from .utils.recover_address import recover_address

def signature_required(func):
    @wraps(func)
    def _wrapped_func(self, request, *args, **kwargs):

        if not (signature := request.data.get("signature")):
            raise Exception(f"Signature not found in request body: '{request.data}'")
        if not (message := request.data.get("message")):
            raise Exception(f"Original message not found in request body: '{request.data}'")

        address = recover_address(message, signature)
        request.address = address
        request.message = message
        request.signature = signature
        return func(self, request, *args, **kwargs)

    return _wrapped_func


from django.contrib import messages
from django.urls import reverse
from django.shortcuts import redirect
from ratelimit.decorators import ratelimit


def login_wrapper(login_func):
    @ratelimit(method='POST', key='ip', rate='5/5m')
    def admin_login(request, **kwargs):
        if getattr(request, 'limited', False):  # was_limited
            messages.error(request, 'Too many login attemps, please wait 5 minutes')
            return redirect(reverse("admin:index"))
        else:
            return login_func(request, **kwargs)

    return admin_login
