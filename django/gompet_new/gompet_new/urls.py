"""
URL configuration for gompet_new project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
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
from django.contrib import admin
from django.urls import path
from django.urls import include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

from django.conf import settings
from django.conf.urls.static import static

from .settings import SPECTACULAR_SETTINGS_V1, SPECTACULAR_SETTINGS_V2


urlpatterns = [
    path('admin/', admin.site.urls),
     
    # OpenAPI schema
    path(
        'api/v1/schema/',
        SpectacularAPIView.as_view(
            custom_settings=SPECTACULAR_SETTINGS_V1
        ),
        name='schema-v1'
    ),
    # Swagger UI (podgląd interaktywny)
    path(
        'api/v1/docs/',
        SpectacularSwaggerView.as_view(
            url_name='schema-v1'
        ),
        name='swagger-ui-v1'
    ),
    # ReDoc UI (alternatywna dokumentacja)
    path(
        'api/v1/redoc/',
        SpectacularRedocView.as_view(
            url_name='schema-v1'
        ),
        name='redoc-v1'
    ),

    # --- V2 ---
    path(
        'api/v2/schema/',
        SpectacularAPIView.as_view(
            custom_settings=SPECTACULAR_SETTINGS_V2
        ),
        name='schema-v2'
    ),
    path(
        'api/v2/docs/',
        SpectacularSwaggerView.as_view(
            url_name='schema-v2'
        ),
        name='swagger-ui-v2'
    ),
    path(
        'api/v2/redoc/',
        SpectacularRedocView.as_view(
            url_name='schema-v2'
        ),
        name='redoc-v2'
    ),


]



urlpatterns += [
    path('animals/', include('animals.urls')),
    path('common/', include('common.urls')),
    path('users/', include('users.urls')),
    path('litters/', include('litters.urls')),
    path('posts/', include('posts.urls')),
    path('articles/', include('articles.urls')),

]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)