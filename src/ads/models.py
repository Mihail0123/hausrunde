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