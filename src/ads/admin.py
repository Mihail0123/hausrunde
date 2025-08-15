from django.contrib import admin
from .models import Ad, Booking

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
