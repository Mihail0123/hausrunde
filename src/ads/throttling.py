from rest_framework.throttling import ScopedRateThrottle

class AdsListThrottle(ScopedRateThrottle):
    scope = "ads_list"

class AdsRetrieveThrottle(ScopedRateThrottle):
    scope = "ads_retrieve"

class AdsAvailabilityThrottle(ScopedRateThrottle):
    scope = "ads_availability"

class AdImageUploadThrottle(ScopedRateThrottle):
    scope = "adimage_upload"

class AdImageReplaceThrottle(ScopedRateThrottle):
    scope = "adimage_replace"

class ScopedRateThrottleIsolated(ScopedRateThrottle):
    """
    Include the resolved rate in the cache key to avoid collisions
    when tests or environments override DEFAULT_THROTTLE_RATES.
    """
    def get_cache_key(self, request, view):
        key = super().get_cache_key(request, view)
        if key is None:
            return None
        return f"{key}:{self.get_rate() or 'none'}"