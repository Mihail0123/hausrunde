from rest_framework import permissions


class IsAdOwnerOrReadOnly(permissions.BasePermission):
    """Read for everyone; write only for ad owner."""
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.owner_id == getattr(request.user, "id", None)


class IsBookingOwnerOrAdOwner(permissions.BasePermission):
    """
    Read allowed for booking tenant or ad owner.
    confirm/reject: only ad owner.
    cancel: only booking tenant.
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return (
                obj.tenant_id == getattr(request.user, "id", None)
                or obj.ad.owner_id == getattr(request.user, "id", None)
            )

        action = getattr(view, "action", None)
        if action in ("confirm", "reject"):
            return obj.ad.owner_id == getattr(request.user, "id", None)
        if action == "cancel":
            return obj.tenant_id == getattr(request.user, "id", None)

        return False


class IsReviewOwnerOrAdmin(permissions.BasePermission):
    """Read for everyone; write only for review author or staff."""
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (obj.tenant_id == user.id or user.is_staff)
        )
