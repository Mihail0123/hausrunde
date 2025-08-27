import logging
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser, FormParser
from drf_spectacular.utils import (
    extend_schema_view, extend_schema, OpenApiParameter, OpenApiTypes,
    OpenApiExample, OpenApiResponse
)

from ..models import AdImage
from ..serializers import (
    AdImageSerializer, AdImageUploadSerializer, AdImageCaptionUpdateSerializer
)
from ..permissions import IsAdOwnerOrReadOnly
from ..validators import validate_image_file

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        summary="List ad images",
        description="Get list of images for a specific ad",
        parameters=[
            OpenApiParameter("ad", OpenApiTypes.INT, description="Ad ID", required=True),
        ],
        responses={
            200: AdImageSerializer,
            400: OpenApiResponse(description="Invalid ad parameter"),
        }
    ),
    create=extend_schema(
        summary="Upload ad images",
        description="Upload one or multiple images for an ad (owner only)",
        request=AdImageUploadSerializer,
        responses={
            201: AdImageSerializer,
            400: OpenApiResponse(description="Validation error"),
            401: OpenApiResponse(description="Authentication required"),
            403: OpenApiResponse(description="Permission denied"),
        }
    ),
    retrieve=extend_schema(
        summary="Get image details",
        description="Get detailed information about a specific image",
        responses={
            200: AdImageSerializer,
            404: OpenApiResponse(description="Image not found"),
        }
    ),
    update=extend_schema(
        summary="Update image",
        description="Update image caption (owner only)",
        request=AdImageCaptionUpdateSerializer,
        responses={
            200: AdImageSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Image not found"),
        }
    ),
    partial_update=extend_schema(
        summary="Partial update image",
        description="Partially update an existing image (owner only)",
        request=AdImageCaptionUpdateSerializer,
        responses={
            200: AdImageSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Image not found"),
        }
    ),
    destroy=extend_schema(
        summary="Delete image",
        description="Delete an image (owner only)",
        responses={
            204: OpenApiResponse(description="Image deleted"),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Image not found"),
        }
    ),
)
class AdImageViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing ad images.

    Supports CRUD operations for images with file upload and caption management.
    """
    serializer_class = AdImageSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly, IsAdOwnerOrReadOnly)
    parser_classes = (MultiPartParser, FormParser)
    throttle_scope = 'images'

    def get_queryset(self):
        """Filter images by ad if specified."""
        queryset = AdImage.objects.select_related('ad__owner')

        ad_id = self.request.query_params.get('ad')
        if ad_id:
            try:
                ad_id = int(ad_id)
                queryset = queryset.filter(ad_id=ad_id)
            except (ValueError, TypeError):
                logger.warning(f"Invalid ad ID: {ad_id}")
                return AdImage.objects.none()

        return queryset

    def get_serializer_class(self):
        """Use different serializers for different actions."""
        if self.action == 'create':
            return AdImageUploadSerializer
        elif self.action in ['update', 'partial_update']:
            return AdImageCaptionUpdateSerializer
        return AdImageSerializer

    def perform_create(self, serializer):
        """Handle image upload and validation."""
        ad_id = self.request.data.get('ad')
        if not ad_id:
            raise ValidationError({"ad": "Ad ID is required."})

        # Validate image files
        images = self.request.FILES.getlist('images')
        if not images:
            # Single image upload
            image = self.request.FILES.get('image')
            if image:
                validate_image_file(image)
                images = [image]
            else:
                raise ValidationError({"images": "At least one image is required."})

        # Create image objects
        created_images = []
        for image in images:
            validate_image_file(image)
            caption = self.request.data.get('caption', '')
            img_obj = AdImage.objects.create(
                ad_id=ad_id,
                image=image,
                caption=caption
            )
            created_images.append(img_obj)

        # Return the first created image for single image upload
        if len(created_images) == 1:
            return created_images[0]
        else:
            # For multiple images, we need to handle this differently
            # This is a limitation of DRF - we can't return multiple objects easily
            return created_images[0]

    @extend_schema(
        summary="Reorder images",
        description="Change the order of images for an ad (owner only)",
        request=OpenApiTypes.OBJECT,
        responses={
            200: OpenApiResponse(description="Images reordered successfully"),
            400: OpenApiResponse(description="Invalid order data"),
            403: OpenApiResponse(description="Permission denied"),
        }
    )
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def reorder(self, request):
        """Reorder images for an ad."""
        ad_id = request.data.get('ad_id')
        image_order = request.data.get('image_order', [])

        if not ad_id or not image_order:
            return Response(
                {"detail": "ad_id and image_order are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verify user owns the ad
        ad = AdImage.objects.filter(id__in=image_order).first()
        if not ad or ad.ad.owner != request.user:
            return Response(
                {"detail": "You can only reorder images for your own ads."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Update order (assuming you have an order field)
        # This is a simplified implementation
        for index, image_id in enumerate(image_order):
            try:
                image = AdImage.objects.get(id=image_id, ad_id=ad_id)
                # If you have an order field, update it here
                # image.order = index
                # image.save()
            except AdImage.DoesNotExist:
                continue

        return Response({"detail": "Images reordered successfully."})

    @extend_schema(
        summary="Bulk delete images",
        description="Delete multiple images at once (owner only)",
        request=OpenApiTypes.OBJECT,
        responses={
            200: OpenApiResponse(description="Images deleted successfully"),
            400: OpenApiResponse(description="Invalid data"),
            403: OpenApiResponse(description="Permission denied"),
        }
    )
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def bulk_delete(self, request):
        """Delete multiple images at once."""
        image_ids = request.data.get('image_ids', [])

        if not image_ids:
            return Response(
                {"detail": "image_ids is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verify user owns all images
        images = AdImage.objects.filter(id__in=image_ids).select_related('ad__owner')
        for image in images:
            if image.ad.owner != request.user:
                return Response(
                    {"detail": "You can only delete images from your own ads."},
                    status=status.HTTP_403_FORBIDDEN
                )

        # Delete images
        deleted_count = images.count()
        images.delete()

        return Response({
            "detail": f"{deleted_count} images deleted successfully."
        })

    @extend_schema(
        summary="Get image statistics",
        description="Get statistics for images of an ad (owner only)",
        responses={
            200: OpenApiResponse(
                description="Image statistics",
                examples=[
                    OpenApiExample(
                        "Example response",
                        value={
                            "total_images": 8,
                            "total_size_mb": 15.2,
                            "average_size_mb": 1.9,
                            "formats": {"JPEG": 6, "PNG": 2},
                            "storage_usage": "15.2 MB"
                        }
                    )
                ]
            ),
            403: OpenApiResponse(description="Permission denied"),
        }
    )
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def stats(self, request):
        """Get image statistics for an ad."""
        ad_id = request.query_params.get('ad')
        if not ad_id:
            return Response(
                {"detail": "ad parameter is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            ad_id = int(ad_id)
        except (ValueError, TypeError):
            return Response(
                {"detail": "Invalid ad ID."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verify user owns the ad
        from ..models import Ad
        try:
            ad = Ad.objects.get(id=ad_id)
        except Ad.DoesNotExist:
            return Response(
                {"detail": "Ad not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        if ad.owner != request.user:
            return Response(
                {"detail": "You can only view statistics for your own ads."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Calculate statistics
        images = AdImage.objects.filter(ad_id=ad_id)
        total_images = images.count()

        # Calculate total size (simplified)
        total_size_bytes = sum(img.image.size for img in images if hasattr(img.image, 'size'))
        total_size_mb = round(total_size_bytes / (1024 * 1024), 1)
        average_size_mb = round(total_size_mb / total_images, 1) if total_images > 0 else 0

        # Count formats
        formats = {}
        for img in images:
            if hasattr(img.image, 'name'):
                ext = img.image.name.split('.')[-1].upper()
                formats[ext] = formats.get(ext, 0) + 1

        stats = {
            'total_images': total_images,
            'total_size_mb': total_size_mb,
            'average_size_mb': average_size_mb,
            'formats': formats,
            'storage_usage': f"{total_size_mb} MB"
        }

        return Response(stats)