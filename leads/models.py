from django.db import models
from django.conf import settings
# Create your models here.

class Lead(models.Model):

    STATUS_CHOICES = [
        ('NEW', 'New'),
        ('CONTACTED', 'Contacted'),
        ('QUALIFIED', 'Qualified'),
        ('LOST', 'Lost'),
    ]

    SOURCE_CHOICES = [
        ('WEBSITE', 'Website'),
        ('REFERRAL', 'Referral'),
        ('DIRECT', 'Direct'),
        ('AD', 'Ad'),
    ]

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)

    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20)
    whatsapp_number = models.CharField(max_length=20, blank=True, null=True)

    gender = models.CharField(max_length=10, blank=True, null=True)
    is_uae_resident = models.BooleanField(default=False)
    visa_status = models.CharField(max_length=50, blank=True, null=True)
    emirates_of_visa = models.CharField(max_length=50, blank=True, null=True)

    salary_scale = models.CharField(max_length=50, blank=True, null=True)
    available_to_everyone = models.BooleanField(default=True)

    source_form = models.CharField(max_length=100, blank=True, null=True)
    need_car_insurance = models.BooleanField(default=False)

    car_year = models.IntegerField(blank=True, null=True)
    car_model = models.CharField(max_length=100, blank=True, null=True)
    car_plate_no = models.CharField(max_length=50, blank=True, null=True)

    status = models.CharField(max_length=20,choices=STATUS_CHOICES,default='NEW')
    current_stage = models.IntegerField(default=1)

    is_favorite = models.BooleanField(default=False)
    progress_score = models.IntegerField(default=0)


    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES
    )


    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    notes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)




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
    
class InsuranceInfo(models.Model):
    lead = models.OneToOneField(
        Lead,
        on_delete=models.CASCADE,
        related_name="insurance_info"
    )

    type_of_health_insurance = models.CharField(max_length=100, null=True, blank=True)
    gender = models.CharField(max_length=10, null=True, blank=True)
    currently_insured = models.BooleanField(null=True, blank=True)
    salary_band = models.CharField(max_length=50, null=True, blank=True)
    emirates_id = models.CharField(max_length=50, null=True, blank=True)
    preferred_hospitals_clinics = models.TextField(null=True, blank=True)
    specific_benefits = models.TextField(null=True, blank=True)
    basic_plan_type = models.CharField(max_length=50, null=True, blank=True)
    co_payment = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return f"Insurance Info for Lead {self.lead.id}"