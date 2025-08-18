from django.contrib import admin
from .models import Ad, Booking, AdImage, Review, SearchQuery, AdView


@admin.register(Ad)
class AdAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'location', 'price', 'rooms', 'housing_type', 'is_active', 'owner', 'created_at')
    list_filter = ('is_active', 'housing_type', 'location', 'created_at')
    search_fields = ('title', 'description', 'location', 'owner__email')
    ordering = ('-created_at',)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'ad', 'tenant', 'date_from', 'date_to', 'status', 'created_at')
    list_filter = ('status', 'date_from', 'date_to', 'created_at')
    search_fields = ('ad__title', 'tenant__email', 'ad__owner__email')
    ordering = ('-created_at',)


@admin.register(AdImage)
class AdImageAdmin(admin.ModelAdmin):
    list_display = ('id', 'ad', 'caption', 'created_at')
    search_fields = ('ad__title', 'caption')
    ordering = ('-created_at',)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'ad', 'tenant', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('ad__title', 'tenant__email', 'text')
    ordering = ('-created_at',)


@admin.register(SearchQuery)
class SearchQueryAdmin(admin.ModelAdmin):
    list_display = ('id', 'q', 'user', 'created_at', 'ip')
    search_fields = ('q', 'user__email', 'user_agent')
    list_filter = ('created_at',)
    ordering = ('-created_at',)


@admin.register(AdView)
class AdViewAdmin(admin.ModelAdmin):
    list_display = ('id', 'ad', 'user', 'created_at', 'ip')
    search_fields = ('ad__title', 'user__email', 'user_agent')
    list_filter = ('created_at',)
    ordering = ('-created_at',)
