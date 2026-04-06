from rest_framework import serializers
from .models import Lead


class LeadListSerializer(serializers.ModelSerializer):

    contact = serializers.SerializerMethodField()
    timestamps = serializers.SerializerMethodField()
    source_info = serializers.SerializerMethodField()
    assignment = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = [
            "id",
            "contact",
            "timestamps",
            "source_info",
            "assignment",
            "is_favorite",
        ]

    # ---- CONTACT ----
    def get_contact(self, obj):
        return {
            "first_name": f"{obj.first_name} {obj.last_name or ''}".strip(),
            "phone": obj.phone,
        }
    
    def get_source_info(self, obj):
        return {
            "source": obj.source,
            "source_form": obj.source_form,
        }

    def get_timestamps(self, obj):
        return {
            "created_at": obj.created_at,
            "modified_at": obj.updated_at,
        }
    def get_assignment(self, obj):
        return {
            # "role": obj.assigned_to.role.name if obj.assigned_to else None,
            "status": obj.status,
            "progress_score": obj.progress_score,
        }
    
from rest_framework import serializers
from .models import Lead


class CreateLeadSerializer(serializers.ModelSerializer):

    source_platform = serializers.CharField(write_only=True)
    source_form = serializers.CharField(write_only=True, required=False)
    source_url = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Lead
        fields = [
            "first_name",
            "last_name",
            "phone",
            "email",
            "source_platform",
            "source_form",
            "source_url",
            "assigned_to",
            "status",
            "progress_score",
            "is_favorite",
            "notes",
        ]

    def create(self, validated_data):
    
        platform = validated_data.pop("source_platform")

        validated_data["source"] = platform

        return Lead.objects.create(**validated_data)


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
    phone_numbers = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = []

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    def get_phone_numbers(self, obj):
        phones = [obj.phone]
        if obj.whatsapp_number:
            phones.append(obj.whatsapp_number)
        return phones

    def to_representation(self, instance):
        return {
            "lead_id": instance.id,
            "status": {
                "current_stage": instance.current_stage,
                "label": instance.status,
                "workflow_steps": [
                    "New Lead",
                    "Assigned",
                    "Non Contactable-1",
                    "Non Contactable-2",
                    "Non Contactable-3",
                    "Contactable",
                    "Requirement Gathering",
                    "Sales Qualified Lead"
                ]
            },
            "personal_info": {
                "full_name": self.get_full_name(instance),
                "email": instance.email,
                "phone_numbers": self.get_phone_numbers(instance),
                "whatsapp_number": instance.whatsapp_number,
                "gender": instance.gender,
                "is_uae_resident": instance.is_uae_resident,
                "visa_status": instance.visa_status,
                "emirates_of_visa": instance.emirates_of_visa
            },
            "financial_info": {
                "salary_scale": instance.salary_scale,
                "available_to_everyone": instance.available_to_everyone
            },
            "insurance_intent": {
                "source_form": instance.source_form,
                "need_car_insurance": instance.need_car_insurance,
                "car_details": {
                    "year": instance.car_year,
                    "model": instance.car_model,
                    "plate_no": instance.car_plate_no
                }
            }
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