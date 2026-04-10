from rest_framework import serializers
from .models import Lead


from .models import InsuranceInfo

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