
from rest_framework import serializers
from .models import Deals

class DealSerializer(serializers.ModelSerializer):
    class Meta:
        model = Deals
        fields = [
            "id",
            "policy_type",
            "customer",
            "premium_amount",
            "stage_id"
        ]