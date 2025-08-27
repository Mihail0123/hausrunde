from django.db import models
from django.conf import settings


class AdView(models.Model):
    ad = models.ForeignKey('Ad', on_delete=models.CASCADE, related_name='views_modules')
    # Authenticated users: dedup by user only; we do not store their IP
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='ad_views'
    )
    # Legacy: keep for backward-compat (do not write to it anymore)
    ip = models.GenericIPAddressField(null=True, blank=True)
    # New: anonymous visitors are deduplicated by hashed IP (salted)
    anon_ip_hash = models.CharField(max_length=64, null=True, blank=True)

    user_agent = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['ad', 'user', 'created_at'], name='adview_user_dedup_idx'),
            models.Index(fields=['ad', 'ip', 'created_at'], name='adview_ip_dedup_idx'),
            models.Index(fields=['ad', 'anon_ip_hash', 'created_at'], name='adview_anonhash_dedup_idx'),
        ]

    def __str__(self):
        who = self.user_id or self.anon_ip_hash or 'anon'
        return f'View ad={self.ad_id} by {who} at {self.created_at:%Y-%m-%d %H:%M:%S}'