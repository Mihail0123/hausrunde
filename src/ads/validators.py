from django.conf import settings
from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError

# Requires Pillow
BYTES_IN_MB = 1024 * 1024


def validate_image_file(uploaded_file):
    """
    Validate a single uploaded image file against:
      1) max file size (MB)
      2) integrity + allowed formats (JPEG/PNG/WEBP by default)
      3) max dimensions (width/height)
    Leaves the file pointer at position 0 for subsequent saving.
    """
    # 1) file size
    max_bytes = int(getattr(settings, "AD_IMAGE_MAX_MB", 5)) * BYTES_IN_MB
    if uploaded_file.size > max_bytes:
        raise ValidationError(f"File too large: max {settings.AD_IMAGE_MAX_MB} MB")

    # 2) format & integrity
    try:
        uploaded_file.seek(0)
        img = Image.open(uploaded_file)
        img.verify()  # integrity check
    except UnidentifiedImageError:
        raise ValidationError("Unsupported or corrupted image")

    # verify() closes the fp; reopen to read size/format
    uploaded_file.seek(0)
    img = Image.open(uploaded_file)

    fmt = (img.format or "").upper()
    if fmt == "JPG":
        fmt = "JPEG"

    allowed = set(getattr(settings, "AD_IMAGE_ALLOWED_FORMATS", {"JPEG", "PNG", "WEBP"}))
    if fmt not in allowed:
        raise ValidationError(f"Unsupported format: {fmt}. Allowed: {', '.join(sorted(allowed))}")

    # 3) dimensions
    w, h = img.size
    max_w = int(getattr(settings, "AD_IMAGE_MAX_WIDTH", 6000))
    max_h = int(getattr(settings, "AD_IMAGE_MAX_HEIGHT", 6000))
    if w > max_w or h > max_h:
        raise ValidationError(f"Image too large: {w}x{h}px (max {max_w}x{max_h}px)")

    # reset fp for saving in the storage
    uploaded_file.seek(0)
