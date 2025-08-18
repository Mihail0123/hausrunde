from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class Ad(models.Model):
    title = models.CharField(max_length=100)
    description = models.TextField()
    location = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2, db_index=True)
    rooms = models.IntegerField(db_index=True)
    housing_type = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    area = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, db_index=True)  # m²
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_demo = models.BooleanField(default=False)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ads',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['price']),
            models.Index(fields=['rooms']),
            models.Index(fields=['area']),
        ]

    def __str__(self):
        return self.title


class AdImage(models.Model):
    ad = models.ForeignKey(Ad, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='ad_images/%Y/%m/%d/')
    caption = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Image #{self.pk} for Ad #{self.ad_id}"


class Review(models.Model):
    ad = models.ForeignKey('Ad', on_delete=models.CASCADE, related_name='reviews')
    tenant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField()
    text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (('tenant', 'ad'),)
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['ad', 'tenant']),
            models.Index(fields=['ad', 'rating']),
        ]

    def __str__(self):
        return f"Review {self.id} on {self.ad_id} by {self.tenant_id}"

    def clean(self):
        if not (1 <= int(self.rating) <= 5):
            from django.core.exceptions import ValidationError
            raise ValidationError({'rating': _('Rating must be between 1 and 5')})


class SearchQuery(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='search_queries'
    )
    q = models.CharField(max_length=255, blank=True, default='')
    filters = models.JSONField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['q']),
        ]
        ordering = ['-created_at']


class Booking(models.Model):
    """Booking request"""
    PENDING = 'PENDING'
    CONFIRMED = 'CONFIRMED'
    CANCELLED = 'CANCELLED'
    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (CONFIRMED, 'Confirmed'),
        (CANCELLED, 'Cancelled'),
    ]

    ad = models.ForeignKey(Ad, on_delete=models.CASCADE, related_name='bookings')
    tenant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bookings')
    date_from = models.DateField()
    date_to = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.tenant} → {self.ad} [{self.status}]"

class AdView(models.Model):
    ad = models.ForeignKey('Ad', on_delete=models.CASCADE, related_name='views')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ad_views'
    )
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['ad', 'created_at']),
        ]
        ordering = ['-created_at']