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