from rest_framework import serializers
from .models import Insurer,QuoteRequest

class QuoteRequestSerializer(serializers.ModelSerializer):
    insurers = serializers.SlugRelatedField(
        many=True,
        slug_field='insurer_id',
        queryset=Insurer.objects.all()
    )

    class Meta:
        model = QuoteRequest
        fields = '__all__'