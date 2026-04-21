from rest_framework import serializers

from .models import Lead
class LeadListSerializer(serializers.ModelSerializer):
    contact = serializers.SerializerMethodField()
    timestamps = serializers.SerializerMethodField()
    source_info = serializers.SerializerMethodField()
    assignment = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = "__all__"  # include all fields

    def get_contact(self, obj):
        return {
            "full_name": obj.name,
            "phone": obj.mobile_number,
            "email": obj.email,
        }

    def get_source_info(self, obj):
        return {
            "source": obj.delivery_channel,
            "product_type": obj.product_type,
        }

    def get_timestamps(self, obj):
        return {
            "created_at": obj.created_at,
            "updated_at": obj.updated_at,
        }

    def get_assignment(self, obj):
        return {
            "status": obj.status,
            "stage": obj.stage,
            "progress_score": obj.progress_score,
            "responsible": obj.responsible.id if obj.responsible else None,
        }
    
from rest_framework import serializers
from .models import Lead

class CreateLeadSerializer(serializers.ModelSerializer):

    class Meta:
        model = Lead
        fields = [
            "name",
            "address",
            "occupation",
            "mobile_number",
            "phone_number",
            "email",
            "product_type",
            "delivery_channel",
            "is_pep",
            "responsible",
            "stage",
            "status",
            "progress_score",
            "is_favorite",
            "notes",
        ]


class LeadStatusUpdateSerializer(serializers.ModelSerializer):

    class Meta:
        model = Lead
        fields = ["status"]

    def validate_status(self, value):
        allowed_status = [choice[0] for choice in Lead.STATUS_CHOICES]

        if value not in allowed_status:
            raise serializers.ValidationError("Invalid status")

        return value


from .models import Lead, LeadActivity


class LeadDetailsSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = "__all__"

    def get_full_name(self, obj):
        return f"{obj.name}"

    def to_representation(self, instance):
        return {
            "lead_id": instance.id,
            "full_name": self.get_full_name(instance),
            "email": instance.email,
            "mobile_number": instance.mobile_number,
            "phone_number": instance.phone_number,
            "address": instance.address,
            "occupation": instance.occupation,
            "product_type": instance.product_type,
            "delivery_channel": instance.delivery_channel,
            "is_pep": instance.is_pep,
            "status": instance.status,
            "stage": instance.stage,
            "progress_score": instance.progress_score,
            "responsible": instance.responsible.id if instance.responsible else None,
            "created_at": instance.created_at,
            "updated_at": instance.updated_at,
            "notes": instance.notes,
        }




class LeadActivitySerializer(serializers.ModelSerializer):

    class Meta:
        model = LeadActivity
        fields = [
            "activity_type",
            "timestamp",
            "description",
            "subject",
            "user_icon"
        ]

    def to_representation(self, instance):
        data = {
            "type": instance.activity_type,
            "timestamp": instance.timestamp,
        }

        if instance.activity_type == "email_event":
            data.update({
                "event": instance.description,
                "subject": instance.subject,
                "user_icon": instance.user_icon
            })

        elif instance.activity_type == "system_prompt":
            data.update({
                "label": instance.subject,
                "description": instance.description
            })

        elif instance.activity_type == "chat_action":
            data.update({
                "action_label": instance.description
            })

        return data
    

class LeadstageUpdateSerializer(serializers.ModelSerializer):

    class Meta:
        model = Lead
        fields = ["stage"]

    def validate_status(self, value):
        allowed_status = [choice[0] for choice in Lead.STAGE_CHOICES]

        if value not in allowed_status:
            raise serializers.ValidationError("Invalid stage")

        return value