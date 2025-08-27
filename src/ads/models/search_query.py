from django.db import models
from django.conf import settings

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
            models.Index(fields=['q'], name='searchquery_q_idx'),
            models.Index(fields=['created_at'], name='searchquery_created_idx'),
        ]
        ordering = ['-created_at']

