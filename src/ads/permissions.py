from rest_framework import permissions

class IsAdOwnerOrReadOnly(permissions.BasePermission):

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.owner == request.user


class IsBookingOwnerOrAdOwner(permissions.BasePermission):
    """
    read allowed for both ad owner and booking tenant
    confirm/reject for ad owner
    cancel for tenant
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return (obj.tenant == request.user) or (obj.ad.owner == request.user)

        action = getattr(view, 'action', None)
        if action in ('confirm', 'reject'):
            return obj.ad.owner == request.user
        if action == 'cancel':
            return obj.tenant == request.user

        return False