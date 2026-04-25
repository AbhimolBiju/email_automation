
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



from documents.models import Document

class DealDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ["id", "document_type", "file", "uploaded_at"]


class DealCreateSerializer(serializers.ModelSerializer):
    documents = serializers.ListField(
        child=serializers.FileField(),
        write_only=True,
        required=False
    )
    document_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
    )
    driving_license_front = serializers.FileField(write_only=True, required=False)
    driving_license_back = serializers.FileField(write_only=True, required=False)
    emirates_id_front = serializers.FileField(write_only=True, required=False)
    emirates_id_back = serializers.FileField(write_only=True, required=False)
    mulkiya_id_front = serializers.FileField(write_only=True, required=False)
    mulkiya_id_back = serializers.FileField(write_only=True, required=False)

    class Meta:
        model = Deal
        fields = "__all__"   # includes all Deal fields + upload fields

    def create(self, validated_data):
        documents = validated_data.pop('documents', [])
        document_ids = validated_data.pop("document_ids", [])
        typed_docs = {
            "driving_license_front": validated_data.pop("driving_license_front", None),
            "driving_license_back": validated_data.pop("driving_license_back", None),
            "emirates_id_front": validated_data.pop("emirates_id_front", None),
            "emirates_id_back": validated_data.pop("emirates_id_back", None),
            "mulkiya_id_front": validated_data.pop("mulkiya_id_front", None),
            "mulkiya_id_back": validated_data.pop("mulkiya_id_back", None),
        }

        # New deals from the create flow should start in
        # "Awaiting Additional Documents" regardless of client input.
        validated_data["stage_id"] = Deal.STAGE_AWAITING_ADDITIONAL_DOCUMENTS

        deal = Deal.objects.create(**validated_data)

        # Keep the Lead.motor_product_id (motor) pointer in sync.
        # Lead.motor_product points to motor_details row.
        if deal.lead_id:
            try:
                lead = deal.lead
                if lead and getattr(lead, "motor_product_id", None) is None:
                    lead.motor_product = deal
                    lead.save(update_fields=["motor_product"])
            except Exception:
                pass

        for doc_type, file in typed_docs.items():
            if file:
                Document.objects.create(
                    motor_deal=deal,
                    document_type=doc_type,
                    file=file,
                    source="deal_form",
                )

        for file in documents:
            Document.objects.create(
                motor_deal=deal,
                document_type="other",
                file=file,
                source="deal_form",
            )

        if document_ids:
            uploaded_documents = Document.objects.filter(id__in=document_ids)
            if uploaded_documents.count() != len(set(document_ids)):
                raise serializers.ValidationError(
                    {"document_ids": ["One or more uploaded documents were not found."]}
                )
            already_attached = uploaded_documents.exclude(motor_deal__isnull=True)
            if already_attached.exists():
                raise serializers.ValidationError(
                    {"document_ids": ["One or more documents are already attached to a deal."]}
                )
            uploaded_documents.update(motor_deal=deal, source="deal_form")

        return deal
    
    
class DealGeneralInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Deal
        fields = '__all__'
        
        

class DealAdditionalFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = Deal
        fields = ['additional_field']
