from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class Review(models.Model):
    # Denormalized fields for simpler queries/annotations on Ad
    ad = models.ForeignKey('Ad', on_delete=models.CASCADE, related_name='reviews')
    tenant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')

    # One review per booking
    booking = models.OneToOneField('Booking', on_delete=models.CASCADE, related_name='review',null=True, blank=True)

    rating = models.PositiveSmallIntegerField()
    text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        # Keep useful indexes for list/aggregate queries
        indexes = [
            models.Index(fields=['ad', 'tenant']),
            models.Index(fields=['ad', 'rating']),
        ]

    def __str__(self):
        return f"Review {self.id} on booking {self.booking_id} (ad {self.ad_id}) by {self.tenant_id}"

    def clean(self):
        """
        Validate business invariants:
        - rating is 1..5
        - booking.ad and booking.tenant must match declared ad/tenant
        """
        from django.core.exceptions import ValidationError

        if not (1 <= int(self.rating) <= 5):
            raise ValidationError({'rating': _('Rating must be between 1 and 5')})

        if self.booking:
            if self.booking.ad_id != self.ad_id:
                raise ValidationError({'booking': _('Booking ad does not match review ad.')})
            if self.booking.tenant_id != self.tenant_id:
                raise ValidationError({'booking': _('Booking tenant does not match review tenant.')})