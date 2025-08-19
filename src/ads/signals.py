# Signal handlers for cleaning up AdImage files on replace and delete.

from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from .models import AdImage


def _safe_delete_file(file_field):
    """Delete underlying file from storage if it exists."""
    try:
        if not file_field:
            return
        storage = file_field.storage
        name = file_field.name
        if name and storage.exists(name):
            storage.delete(name)
    except Exception:
        # Never break main flow because of FS issues
        pass


@receiver(post_delete, sender=AdImage)
def adimage_post_delete(sender, instance: AdImage, **kwargs):
    """Remove file from storage when AdImage row is deleted."""
    _safe_delete_file(instance.image)


@receiver(pre_save, sender=AdImage)
def adimage_pre_save_replace(sender, instance: AdImage, **kwargs):
    """
    If image file changes on update, delete the previous file from storage.
    """
    if not instance.pk:
        return  # new object, nothing to replace
    try:
        old = AdImage.objects.get(pk=instance.pk)
    except AdImage.DoesNotExist:
        return
    old_file = getattr(old, "image", None)
    new_file = getattr(instance, "image", None)
    # If the file path changed, remove the previous one
    if old_file and new_file and old_file.name != new_file.name:
        _safe_delete_file(old_file)
