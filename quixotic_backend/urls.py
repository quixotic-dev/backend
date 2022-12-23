"""quixotic_backend URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
import os

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from api.decorators import login_wrapper
from api.views import celery_health, default_view, error_view, heath_view
from api.viewsets import router as api_router
from batch_processing.viewset import router as batch_processing_router
from launchpad.viewsets import router as launchpad_router
from public_api.viewsets import router as public_router

admin.autodiscover()
admin.site.login = login_wrapper(admin.site.login)  # rate limit

if os.environ.get("IS_EXTERNAL_API"):
    urlpatterns = [
        path("", default_view),
        path("api/v1/", include(public_router.urls)),
    ]
else:
    urlpatterns = [
        path("", default_view),
        path("health/", heath_view),
        path("celery_health/", celery_health),
        path("api/", include(api_router.urls)),
        path("launchpad/", include(launchpad_router.urls)),
        path("batch/", include(batch_processing_router.urls)),
        path("admin/", admin.site.urls),
    ]

if settings.DEBUG:
    urlpatterns.append(
        path("__debug__/", include("debug_toolbar.urls")),
    )
    urlpatterns.append(path("error", error_view))
