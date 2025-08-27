from django.db import models
from django.conf import settings

from src.ads.models import Ad


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
        indexes = [
            models.Index(
                fields=['ad', 'status', 'date_from', 'date_to'],
                name='booking_overlap_idx',
            ),
        ]


    def __str__(self):
        return f"{self.tenant} → {self.ad} [{self.status}]"
