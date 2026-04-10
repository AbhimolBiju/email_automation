from django.db import models
from leads.models import Lead
# Create your models here.
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