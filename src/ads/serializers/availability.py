from rest_framework import serializers
from src.ads.models import Booking

class AvailabilityItemSerializer(serializers.Serializer):
    """Public shape for busy date ranges."""
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    status = serializers.ChoiceField(choices=Booking.STATUS_CHOICES)