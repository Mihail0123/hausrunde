from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import CustomUserViewSet, LoginView, LogoutView, DebugTokenView

router = DefaultRouter()
router.register(r'users', CustomUserViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('debug-tokens/', DebugTokenView.as_view(), name='debug'),
]