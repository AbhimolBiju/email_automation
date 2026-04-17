
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
            return obj.lead.name
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
            return obj.lead.name
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
    
    

class StageOptionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    label = serializers.CharField()


class SortOptionSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()


class FilterSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    type = serializers.CharField()
    options = StageOptionSerializer(many=True, required=False)


class FilterOptionsResponseSerializer(serializers.Serializer):
    sort_options = SortOptionSerializer(many=True)
    filters = FilterSerializer(many=True)
    
    
    
class DealSerializer(serializers.ModelSerializer):
    class Meta:
        model = Deal
        fields = '__all__'



from .models import  DealDocument

class DealDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = DealDocument
        fields = ['id', 'file', 'uploaded_at']


class DealCreateSerializer(serializers.ModelSerializer):
    documents = serializers.ListField(
        child=serializers.FileField(),
        write_only=True,
        required=False
    )

    class Meta:
        model = Deal
        fields = '__all__'   # includes all Deal fields + documents

    def create(self, validated_data):
        documents = validated_data.pop('documents', [])

        deal = Deal.objects.create(**validated_data)

        for file in documents:
            DealDocument.objects.create(deal=deal, file=file)

        return deal
    
    
class DealGeneralInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Deal
        fields = '__all__'
        
        

class DealAdditionalFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = Deal
        fields = ['additional_field']