from rest_framework import serializers
from .models import InsuranceInfo, InsuranceProvider, QuoteBatch, QuoteResult

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


class QuoteResultSerializer(serializers.ModelSerializer):
    provider = serializers.CharField(source="provider.code", read_only=True)
    provider_name = serializers.SerializerMethodField()
    logo = serializers.SerializerMethodField()

    def get_provider_name(self, obj):
        return obj.provider_name or obj.provider.name

    def get_logo(self, obj):
        config = obj.provider.extra_config if isinstance(obj.provider.extra_config, dict) else {}
        return config.get("logo_url", "")

    class Meta:
        model = QuoteResult
        fields = [
            "id",
            "provider",
            "provider_name",
            "logo",
            "premium",
            "vat",
            "total",
            "currency",
            "plan_name",
            "response_time_ms",
            "ranking",
            "coverage_score",
            "status",
            "error_message",
            "normalized_response",
            "raw_response",
            "is_recommended",
            "is_cheapest",
            "is_best_value",
            "created_at",
        ]


class QuoteBatchListSerializer(serializers.ModelSerializer):
    deal_id = serializers.IntegerField(source="deal.id", read_only=True)
    lead_id = serializers.IntegerField(source="lead.id", read_only=True)
    customer_name = serializers.SerializerMethodField()
    vehicle = serializers.SerializerMethodField()
    product = serializers.SerializerMethodField()
    best_provider = serializers.CharField(source="best_provider.name", read_only=True)
    result_count = serializers.IntegerField(read_only=True)

    def get_customer_name(self, obj):
        return obj.lead.name if obj.lead else ""

    def get_vehicle(self, obj):
        deal = obj.deal
        parts = [str(value).strip() for value in [deal.make_id, deal.model_id, deal.model_year] if value not in (None, "")]
        return " ".join(parts) or (deal.reg_number or "")

    def get_product(self, obj):
        return obj.deal.get_sub_type_display() or obj.deal.get_insurance_type_display() or obj.deal.insurance_type or "Motor"

    class Meta:
        model = QuoteBatch
        fields = [
            "id",
            "reference_no",
            "deal_id",
            "lead_id",
            "customer_name",
            "vehicle",
            "product",
            "requested_at",
            "best_provider",
            "best_total",
            "status",
            "cache_expires_at",
            "result_count",
        ]


class QuoteBatchDetailSerializer(serializers.ModelSerializer):
    deal_id = serializers.IntegerField(source="deal.id", read_only=True)
    lead_id = serializers.IntegerField(source="lead.id", read_only=True)
    customer_name = serializers.SerializerMethodField()
    product = serializers.SerializerMethodField()
    vehicle = serializers.SerializerMethodField()
    stage = serializers.SerializerMethodField()
    best_provider = serializers.CharField(source="best_provider.name", read_only=True)
    results = QuoteResultSerializer(many=True, read_only=True)

    def get_customer_name(self, obj):
        return obj.lead.name if obj.lead else ""

    def get_product(self, obj):
        return obj.deal.get_sub_type_display() or obj.deal.get_insurance_type_display() or obj.deal.insurance_type or "Motor"

    def get_vehicle(self, obj):
        deal = obj.deal
        parts = [str(value).strip() for value in [deal.make_id, deal.model_id, deal.model_year] if value not in (None, "")]
        return " ".join(parts) or (deal.reg_number or "")

    def get_stage(self, obj):
        return obj.deal.get_stage_id_display()

    class Meta:
        model = QuoteBatch
        fields = [
            "id",
            "reference_no",
            "deal_id",
            "lead_id",
            "customer_name",
            "product",
            "vehicle",
            "requested_at",
            "status",
            "stage",
            "best_provider",
            "best_total",
            "cache_expires_at",
            "results",
        ]
