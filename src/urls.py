from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from django.conf import settings
from django.conf.urls.static import static

from src.users.views import TokenObtainPairThrottleView
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    # Demo frontend
    path("frontend/", TemplateView.as_view(template_name="frontend/index.html")),

    # Django admin
    path("admin/", admin.site.urls),

    # JWT auth with throttling
    path("api/token/", TokenObtainPairThrottleView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    # API apps with namespace
    path("api/users/", include(("src.users.urls", "users"), namespace="users")),
    path("api/ads/", include(("src.ads.urls", "ads"), namespace="ads")),

    # OpenAPI / Swagger
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]

# static in dev mode
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
