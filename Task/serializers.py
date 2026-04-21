from deals.models import Lead
from rest_framework import serializers

from .models import Task

class WorkflowStatsSerializer(serializers.Serializer):
    total_tasks = serializers.IntegerField()
    pending_customer = serializers.IntegerField()
    pending_underwriter = serializers.IntegerField()
    completed_tasks = serializers.IntegerField()




class TaskSerializer(serializers.ModelSerializer):

    class Meta:
        model = Task
        fields = "__all__"


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

    



