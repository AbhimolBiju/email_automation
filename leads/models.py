from django.db import models
from django.conf import settings
# Create your models here.
from django.db import models
from django.conf import settings


class Lead(models.Model):

    YES_NO_CHOICES = [
        ('Y', 'Yes'),
        ('N', 'No'),
    ]
    # lead_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    
    address = models.TextField(blank=True, null=True)

    # Occupation (string)
    occupation = models.CharField(max_length=100, blank=True, null=True)

    # Mobile Number (string)
    mobile_number = models.CharField(max_length=20)

    # Phone Number (string)
    phone_number = models.CharField(max_length=20, blank=True, null=True)

    # Email (string)
    email = models.EmailField(unique=True)

    # Product Type (string)
    product_type = models.CharField(max_length=100)

    # Delivery Channel / Lead Source (string)
    lead_source = models.CharField(max_length=100, blank=True, null=True)

    # PEP (Y/N)
    pep = models.CharField(max_length=1, choices=YES_NO_CHOICES, default='N')

    # Responsible (assigned to whom)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    # Stage (Lead Stages)
    stage = models.CharField(max_length=50)

    # Creation Date
    created_at = models.DateTimeField(auto_now_add=True)

    # Modified Date
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.lead_id} - {self.name}"

class LeadActivity(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE)

    activity_type = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    subject = models.CharField(max_length=255, blank=True, null=True)

    timestamp = models.DateTimeField(auto_now_add=True)
    user_icon = models.URLField(blank=True, null=True)

from django.conf import settings

class Note(models.Model):
    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name="comments"
    )

    content = models.TextField()
    is_internal = models.BooleanField(default=False)
    mentions = models.JSONField(default=list, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    created_at = models.DateTimeField(auto_now_add=True)



from .models import Lead


class Task(models.Model):

    TASK_TYPE_CHOICES = [
        ("Call", "Call"),
        ("Meeting", "Meeting"),
        ("Email", "Email"),
        ("Follow Up", "Follow Up"),
    ]

    task_type = models.CharField(
        max_length=50,
        choices=TASK_TYPE_CHOICES
    )

    due_date = models.DateTimeField()

    description = models.TextField()

    # ✅ Lead ForeignKey (NEW)
    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name="tasks"
    )

    # ✅ Assigned user
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assigned_tasks"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.task_type} - {self.assigned_to}"
    
# class InsuranceInfo(models.Model):
#     lead = models.OneToOneField(
#         Lead,
#         on_delete=models.CASCADE,
#         related_name="insurance_info"
#     )

#     type_of_health_insurance = models.CharField(max_length=100, null=True, blank=True)
#     gender = models.CharField(max_length=10, null=True, blank=True)
#     currently_insured = models.BooleanField(null=True, blank=True)
#     salary_band = models.CharField(max_length=50, null=True, blank=True)
#     emirates_id = models.CharField(max_length=50, null=True, blank=True)
#     preferred_hospitals_clinics = models.TextField(null=True, blank=True)
#     specific_benefits = models.TextField(null=True, blank=True)
#     basic_plan_type = models.CharField(max_length=50, null=True, blank=True)
#     co_payment = models.CharField(max_length=50, null=True, blank=True)

#     def __str__(self):
#         return f"Insurance Info for Lead {self.lead.id}"