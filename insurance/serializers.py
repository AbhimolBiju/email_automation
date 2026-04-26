from rest_framework import serializers
from .models import InsuranceInfo, InsuranceProvider

class InsuranceInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = InsuranceInfo
        fields = [
            "type_of_health_insurance",
            "gender",
            "currently_insured",
            "salary_band",
            "emirates_id",
            "preferred_hospitals_clinics",
            "specific_benefits",
            "basic_plan_type",
            "co_payment",
        ]


class InsuranceProviderSerializer(serializers.ModelSerializer):
    masked_api_key = serializers.CharField(read_only=True)
    masked_password = serializers.CharField(read_only=True)
    extra_config_keys = serializers.SerializerMethodField()

    def get_extra_config_keys(self, obj):
        config = obj.extra_config if isinstance(obj.extra_config, dict) else {}
        return sorted(config.keys())

    class Meta:
        model = InsuranceProvider
        fields = [
            "id",
            "name",
            "code",
            "base_url",
            "username",
            "extra_config_keys",
            "timeout",
            "priority",
            "is_active",
            "provider_class",
            "created_at",
            "updated_at",
            "masked_api_key",
            "masked_password",
        ]
