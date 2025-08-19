from rest_framework.throttling import ScopedRateThrottle

class AuthLoginThrottle(ScopedRateThrottle):
    scope = "auth_login"
