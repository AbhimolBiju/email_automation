from rest_framework import serializers
from .models import Insurer,QuoteRequest,Quote

class QuoteRequestSerializer(serializers.ModelSerializer):
    insurers = serializers.SlugRelatedField(
        many=True,
        slug_field='insurer_id',
        queryset=Insurer.objects.all()
    )

    class Meta:
        model = QuoteRequest
        fields = '__all__'


class ProviderSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source="Insurer")

    class Meta:
        model = Quote
        fields = [
            "provider_name",
            "plan_name",
            "premium",
            "base_price",
            "vat",
            "currency",
            "badge",
            "buy_now_url",
            "vehicle_details",
            "benefits",
            "optional_covers",
        ]

class QuoteComparisonSerializer(serializers.Serializer):
    customer = serializers.DictField()
    providers = ProviderSerializer(many=True)
    