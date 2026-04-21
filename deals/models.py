from django.db import models
from django.conf import settings
from leads.models import Lead



class Deal(models.Model):

    STAGE_CHOICES = [
        (1, "Potential Customer"),
        (2, "Awaiting Additional Documents"),
        (3, "Quotation"),
        (4, "Follow up"),
        (5, "High Value Leads"),
        (6, "Hot/Responded"),
        (7, "Documentation Request"),
        (8, "Insurer Submission"),
        (9, "Pending with Insurer"),
        (10, "Payment Collection"),
        (11, "Payment Pending"),
        (12, "Payment Done"),
        (13, "Policy Issuance"),
        (14, "Billing"),
        (15, "Lost Cases & Future Prospects"),
    ]

    document_lists = models.TextField(blank=True, null=True)

    lead = models.ForeignKey(
        Lead,
        on_delete=models.SET_NULL,
        null=True,
        related_name='deals'
    )

    nationality = models.CharField(max_length=100, blank=True, null=True)
    emirates_id = models.CharField(max_length=100, blank=True, null=True)

    id_expiry_dt = models.DateField(blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)

    gender = models.CharField(max_length=20, blank=True, null=True)
    emirate = models.CharField(max_length=100, blank=True, null=True)

    license_no = models.CharField(max_length=100, blank=True, null=True)
    license_from_dt = models.DateField(blank=True, null=True)
    license_to_dt = models.DateField(blank=True, null=True)

    chassis_number = models.CharField(max_length=100, blank=True, null=True)  # VIN
    reg_number = models.CharField(max_length=50, blank=True, null=True)
    reg_dt = models.DateField(blank=True, null=True)

    plate_code = models.CharField(max_length=50, blank=True, null=True)
    plate_source = models.CharField(max_length=100, blank=True, null=True)

    tcf_number = models.CharField(max_length=100, blank=True, null=True)
    ncd_years = models.IntegerField(blank=True, null=True)
    traffic_tran_type = models.CharField(max_length=100, blank=True, null=True)

    is_veh_brand_new = models.BooleanField(default=False)
    agency_repair = models.BooleanField(default=False)

    model_year = models.IntegerField(blank=True, null=True)

    make_id = models.CharField(max_length=100, blank=True, null=True)
    model_id = models.CharField(max_length=100, blank=True, null=True)
    trim_id = models.CharField(max_length=100, blank=True, null=True)

    body_type_id = models.CharField(max_length=100, blank=True, null=True)
    engine_capacity_id = models.CharField(max_length=100, blank=True, null=True)
    transmission_id = models.CharField(max_length=100, blank=True, null=True)

    is_gcc_spec = models.BooleanField(default=False)

    mileage = models.IntegerField(blank=True, null=True)

    valuation_date = models.DateField(blank=True, null=True)

    stage_id = models.IntegerField(
        choices=STAGE_CHOICES,
        default=1
    )
    additional_field = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Deal {self.id} - {self.reg_number or 'No Reg'}"
    
    
class DealDocument(models.Model):
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name='documents')
    file = models.FileField(upload_to='deal_documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    