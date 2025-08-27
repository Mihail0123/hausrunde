from django.db import models
from django.conf import settings


class Ad(models.Model):
    class HousingType(models.TextChoices):
        APARTMENT = "apartment", "Apartment"
        HOUSE = "house", "House"
        STUDIO = "studio", "Studio"
        LOFT = "loft", "Loft"
        ROOM = "room", "Room"
        TOWNHOUSE = "townhouse", "Townhouse"
        VILLA = "villa", "Villa"

    title = models.CharField(max_length=100)
    description = models.TextField()
    location = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2, db_index=True)
    rooms = models.IntegerField(db_index=True)
    housing_type = models.CharField(
        max_length=20,
        choices=HousingType.choices,
        default=HousingType.APARTMENT,
    )
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
            models.Index(fields=['is_active', 'created_at'], name='ad_active_created_idx'),
            models.Index(fields=['latitude', 'longitude'], name='ad_lat_lon_idx'),
            models.Index(fields=['housing_type'], name='ad_housing_type_idx'),
        ]

    def __str__(self):
        return self.title