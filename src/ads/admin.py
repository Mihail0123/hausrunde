from django.contrib import admin
from .models import Ad, AdImage, Booking, Review, SearchQuery, AdView

@admin.register(Ad)
class AdAdmin(admin.ModelAdmin):
    list_display = ('id','title','location','price','rooms','housing_type','is_active','owner','created_at')
    list_filter = ('is_active','housing_type','rooms')
    search_fields = ('id','title','location','description','owner__email')
    autocomplete_fields = ('owner',)
    readonly_fields = ('created_at','updated_at')
    ordering = ('-created_at',)
    list_select_related = ('owner',)

@admin.register(AdImage)
class AdImageAdmin(admin.ModelAdmin):
    list_display = ('id','ad','caption','created_at')
    search_fields = ('caption','ad__title','ad__id')
    autocomplete_fields = ('ad',)
    readonly_fields = ('created_at',)
    list_select_related = ('ad',)

@admin.action(description="Confirm selected bookings")
def confirm_bookings(modeladmin, request, qs):
    qs.update(status='CONFIRMED')

@admin.action(description="Cancel/Reject selected bookings")
def cancel_bookings(modeladmin, request, qs):
    qs.update(status='CANCELLED')

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    """
    Show booking inbox clearly:
    - ad owner email as a separate column
    - tenant email
    - quick filters and fast queries
    """
    list_display = (
        "id",
        "ad",                 # title
        "ad_owner_email",     # owner of the ad
        "tenant_email",       # tenant
        "date_from",
        "date_to",
        "status",
        "created_at",
    )
    # Make both id and ad clickable (navigate to Booking / Ad quickly)
    list_display_links = ("id", "ad")

    # Speed up list view; avoid N+1
    list_select_related = ("ad", "ad__owner", "tenant")

    # Useful filters/search for inbox
    list_filter = ("status",)
    search_fields = (
        "ad__title",
        "ad__owner__email",
        "tenant__email",
    )
    ordering = ("-created_at",)

    @admin.display(ordering="ad__owner__email", description="Owner")
    def ad_owner_email(self, obj: Booking):
        """Ad owner email for quick triage."""
        owner = getattr(obj.ad, "owner", None)
        return getattr(owner, "email", None)

    @admin.display(ordering="tenant__email", description="Tenant")
    def tenant_email(self, obj: Booking):
        """Tenant email (requestor)."""
        tenant = getattr(obj, "tenant", None)
        return getattr(tenant, "email", None)

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('id','ad','tenant','rating','created_at')
    list_filter = ('rating',)
    search_fields = ('ad__title','tenant__email')
    autocomplete_fields = ('ad','tenant')
    list_select_related = ('ad','tenant')

@admin.register(SearchQuery)
class SearchQueryAdmin(admin.ModelAdmin):
    list_display = ('id','q','user','ip','created_at')
    list_filter = ('created_at',)
    search_fields = ('q','user__email','ip')
    autocomplete_fields = ('user',)
    readonly_fields = ('filters','user_agent','created_at')
    ordering = ('-created_at',)
    list_select_related = ('user',)

@admin.register(AdView)
class AdViewAdmin(admin.ModelAdmin):
    list_display = ('id','ad','user','ip','created_at')
    list_filter = ('created_at',)
    search_fields = ('ad__title','user__email','ip')
    autocomplete_fields = ('ad','user')
    readonly_fields = ('user_agent','created_at')
    list_select_related = ('ad','user')