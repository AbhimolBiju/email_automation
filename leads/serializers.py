from rest_framework import serializers

from .models import Lead, LeadActivity, Notification
from deals.models import Deal


ASSIGNABLE_ROLES = ("underwriter", "telecallers", "superadmin")


class LeadListSerializer(serializers.ModelSerializer):
    contact = serializers.SerializerMethodField()
    timestamps = serializers.SerializerMethodField()
    source_info = serializers.SerializerMethodField()
    assignment = serializers.SerializerMethodField()
    insurance_type = serializers.SerializerMethodField()
    sub_type = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = "__all__"

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
        responsible_name = None
        responsible_user = None

        if obj.responsible:
            full_name = obj.responsible.get_full_name().strip()
            responsible_name = full_name or obj.responsible.username

            responsible_user = {
                "id": obj.responsible.id,
                "username": obj.responsible.username,
                "full_name": responsible_name,
            }

        return {
            "status": obj.status,
            "stage": obj.stage,
            "progress_score": obj.progress_score,
            "responsible": responsible_user,
            "responsible_name": responsible_name,
        }

    def get_insurance_type(self, obj):
        motor = getattr(obj, "motor_product", None)
        return getattr(motor, "insurance_type", None) if motor else None

    def get_sub_type(self, obj):
        motor = getattr(obj, "motor_product", None)
        return getattr(motor, "sub_type", None) if motor else None


class CreateLeadSerializer(serializers.ModelSerializer):

    insurance_type = serializers.ChoiceField(
        choices=Lead.INSURANCE_TYPE,
        required=False,
        allow_null=True
    )

    sub_type = serializers.ChoiceField(
        choices=Lead.SUB_TYPE_CHOICES,
        required=False,
        allow_null=True
    )

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
            "insurance_type",
            "sub_type",
            "delivery_channel",
            "is_pep",
            "responsible",
            "stage",
            "status",
            "progress_score",
            "is_favorite",
            "source",
            "notes",
        ]

    def validate_responsible(self, value):

        if not value:
            return value

        from .assignment import is_assignable_user

        if not is_assignable_user(value.pk):
            raise serializers.ValidationError(
                "Lead can only be assigned to underwriter, telecallers, or superadmin users."
            )

        return value

    def create(self, validated_data):

        insurance_type = validated_data.pop("insurance_type", None)
        sub_type = validated_data.pop("sub_type", None)

        lead = Lead.objects.create(**validated_data)

        if lead.product_type == "motor" and (insurance_type or sub_type):

            motor = Deal.objects.create(
                lead=lead,
                insurance_type=insurance_type,
                sub_type=sub_type,
                stage_id=1,
            )

            lead.motor_product = motor
            lead.save(update_fields=["motor_product"])

        return lead


class LeadStatusUpdateSerializer(serializers.ModelSerializer):

    class Meta:
        model = Lead
        fields = ["status"]

    def validate_status(self, value):

        allowed_status = [choice[0] for choice in Lead.STATUS_CHOICES]

        if value not in allowed_status:
            raise serializers.ValidationError("Invalid status")

        return value


class LeadDetailsSerializer(serializers.ModelSerializer):

    full_name = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = "__all__"

    def get_full_name(self, obj):
        return f"{obj.name}"

    def to_representation(self, instance):

        responsible_name = None
        responsible_user = None

        if instance.responsible:

            full_name = instance.responsible.get_full_name().strip()
            responsible_name = full_name or instance.responsible.username

            responsible_user = {
                "id": instance.responsible.id,
                "username": instance.responsible.username,
                "full_name": responsible_name,
            }

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
            "responsible": responsible_user,
            "responsible_name": responsible_name,
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
            "user_icon",
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
                "user_icon": instance.user_icon,
            })

        elif instance.activity_type == "system_prompt":

            data.update({
                "label": instance.subject,
                "description": instance.description,
            })

        elif instance.activity_type == "chat_action":

            data.update({
                "action_label": instance.description,
            })

        return data


class LeadstageUpdateSerializer(serializers.ModelSerializer):

    class Meta:
        model = Lead
        fields = ["stage"]

    def validate_stage(self, value):

        allowed_stage = [choice[0] for choice in Lead.STAGE_CHOICES]

        if value not in allowed_stage:
            raise serializers.ValidationError("Invalid stage")

        return value


class NotificationSerializer(serializers.ModelSerializer):

    class Meta:
        model = Notification
        fields = "__all__"