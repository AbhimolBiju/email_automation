
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


class DealDetailSerializer(serializers.ModelSerializer):
    lead = serializers.SerializerMethodField()
    documents = serializers.SerializerMethodField()
    stage_label = serializers.SerializerMethodField()

    class Meta:
        model = Deal
        fields = "__all__"

    def get_lead(self, obj):
        if not obj.lead:
            return None
        responsible = obj.lead.responsible
        responsible_name = ""
        if responsible:
            responsible_name = (
                responsible.get_full_name()
                or responsible.username
                or responsible.email
            )
        return {
            "id": obj.lead.id,
            "name": obj.lead.name,
            "email": obj.lead.email,
            "mobile_number": obj.lead.mobile_number,
            "phone_number": obj.lead.phone_number,
            "product_type": obj.lead.product_type,
            "delivery_channel": obj.lead.delivery_channel,
            "status": obj.lead.status,
            "stage": obj.lead.stage,
            "responsible": responsible_name,
            "created_at": obj.lead.created_at,
            "updated_at": obj.lead.updated_at,
        }

    def get_documents(self, obj):
        return [
            {
                "id": document.id,
                "document_type": document.document_type,
                "file": document.file.url if document.file else None,
                "file_name": document.name,
                "uploaded_at": document.uploaded_at,
                "ocr_status": document.ocr_status,
                "ocr_data": document.ocr_data,
            }
            for document in obj.shared_documents.filter(
                status__in=[
                    Document.STATUS_PENDING,
                    Document.STATUS_VERIFIED,
                ]
            )
        ]

    def get_stage_label(self, obj):
        return dict(Deal.STAGE_CHOICES).get(obj.stage_id, "")


class DealUpdateSerializer(serializers.ModelSerializer):
    document_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
    )
    name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    email = serializers.EmailField(write_only=True, required=False, allow_blank=True)
    mobile_number = serializers.CharField(write_only=True, required=False, allow_blank=True)
    phone_number = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Deal
        fields = "__all__"
        extra_kwargs = {
            "lead": {"required": False, "allow_null": True},
        }

    def update(self, instance, validated_data):
        document_ids = validated_data.pop("document_ids", [])
        lead_name = validated_data.pop("name", None)
        lead_email = validated_data.pop("email", None)
        lead_mobile = validated_data.pop("mobile_number", None)
        lead_phone = validated_data.pop("phone_number", None)

        validated_data["stage_id"] = Deal.STAGE_AWAITING_ADDITIONAL_DOCUMENTS

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if instance.lead_id:
            lead = instance.lead
            changed_fields = []
            if lead_name is not None and lead.name != lead_name:
                lead.name = lead_name
                changed_fields.append("name")
            if lead_email is not None and lead.email != lead_email:
                lead.email = lead_email
                changed_fields.append("email")
            if lead_mobile is not None and lead.mobile_number != lead_mobile:
                lead.mobile_number = lead_mobile
                changed_fields.append("mobile_number")
            if lead_phone is not None and lead.phone_number != lead_phone:
                lead.phone_number = lead_phone
                changed_fields.append("phone_number")
            elif lead_mobile is not None and lead.phone_number != lead_mobile:
                lead.phone_number = lead_mobile
                changed_fields.append("phone_number")

            if changed_fields:
                changed_fields.append("updated_at")
                lead.save(update_fields=changed_fields)

        if document_ids:
            uploaded_documents = Document.objects.filter(id__in=document_ids)
            if uploaded_documents.count() != len(set(document_ids)):
                raise serializers.ValidationError(
                    {"document_ids": ["One or more uploaded documents were not found."]}
                )
            already_attached = uploaded_documents.exclude(
                motor_deal__isnull=True,
            ).exclude(motor_deal=instance)
            if already_attached.exists():
                raise serializers.ValidationError(
                    {"document_ids": ["One or more documents are already attached to another deal."]}
                )
            uploaded_documents.update(motor_deal=instance, source="deal_form")

        return instance


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
