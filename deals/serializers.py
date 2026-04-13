
from rest_framework import serializers
from .models import Deal


from rest_framework import serializers
from .models import Deal

class DealListSerializer(serializers.ModelSerializer):

    customer_name = serializers.SerializerMethodField()

    class Meta:
        model = Deal
        fields = [
            "id",
            "customer_name",
            "reg_number",
            "emirates_id",
            "stage_id",
            "created_at"
        ]

    def get_customer_name(self, obj):
        if obj.lead:
            return f"{obj.lead.first_name} {obj.lead.last_name}"
        return ""

class PipelineStageSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    label = serializers.CharField()
    count = serializers.IntegerField()





class DealExportSerializer(serializers.ModelSerializer):
    customer_name = serializers.SerializerMethodField()
    stage_name = serializers.SerializerMethodField()

    class Meta:
        model = Deal
        fields = [
            "id",
            "customer_name",
            "nationality",
            "emirates_id",
            "reg_number",
            "stage_id",
            "stage_name",
            "created_at"
        ]

    def get_customer_name(self, obj):
        if obj.lead:
            return f"{obj.lead.first_name} {obj.lead.last_name}"
        return ""

    def get_stage_name(self, obj):
        return dict(Deal.STAGE_CHOICES).get(obj.stage_id)




class DealStageUpdateSerializer(serializers.Serializer):
    new_stage_id = serializers.IntegerField()
    reason = serializers.CharField(required=False, allow_blank=True)

    def validate_new_stage_id(self, value):
        valid_stage_ids = [stage[0] for stage in Deal.STAGE_CHOICES]
        if value not in valid_stage_ids:
            raise serializers.ValidationError("Invalid stage id")
        return value