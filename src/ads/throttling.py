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
