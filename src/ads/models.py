from django.db import models
from django.conf import settings

class Ad(models.Model):
    title = models.CharField(max_length=100)
    description = models.TextField()
    location = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    rooms = models.IntegerField()
    housing_type = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ads',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


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