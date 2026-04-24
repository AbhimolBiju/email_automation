from rest_framework import serializers
from .models import Policy, PolicyInsurer
from Quote.models import QuoteRequest


class QuoteRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuoteRequest
        fields = '__all__'


class PolicyInsurerSerializer(serializers.ModelSerializer):
    insurer_name = serializers.CharField(source='insurer.name', read_only=True)
    quote = QuoteRequestSerializer(source='quote_request', read_only=True)

    class Meta:
        model = PolicyInsurer
        fields = [
            'id',
            'insurer_name',
            'premium',
            'payment_status',
            'status',
            'method',
            'quote'
        ]


class PolicyListSerializer(serializers.ModelSerializer):
    insurers = PolicyInsurerSerializer(many=True)

    class Meta:
        model = Policy
        fields = [
            'id',
            'policy_id',
            'customer_name',
            'product_type',
            'issue_date',
            'insurers'
        ]

from rest_framework import serializers
from .models import AdditionalDocument

from rest_framework import serializers
from .models import AdditionalDocument

def validate_file_size(value):
    max_size = 2 * 1024 * 1024  # 2MB
    if value.size > max_size:
        raise serializers.ValidationError("File size should not exceed 2MB")
    return value

class AdditionalDocumentSerializer(serializers.ModelSerializer):
    file = serializers.FileField(validators=[validate_file_size])

    class Meta:
        model = AdditionalDocument
        fields = '__all__'
        read_only_fields = ['id', 'uploaded_at']