from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)
from django.conf import settings
from django.conf.urls.static import static

from src.users.views import (
    ThrottledTokenObtainPairView,
    ThrottledTokenRefreshView,
)

urlpatterns = [
    path("admin/", admin.site.urls),

    # OpenAPI / Swagger / Redoc
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),

    # API
    path("api/", include("src.ads.urls", namespace="ads")),
    path("api/auth/", include("src.users.urls", namespace="users")),
    path('api/auth/token/', ThrottledTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/', ThrottledTokenRefreshView.as_view(), name='token_refresh'),

    # Front
    path("", TemplateView.as_view(template_name="frontend/index.html"), name="front-index"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
