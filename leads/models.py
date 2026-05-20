from django.conf import settings
from django.db import models

class GeneralDetails(models.Model):
    """
    Product-specific details for product_type="general".
    Add fields here as your general product flow evolves.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "general_details"


class MedicalDetails(models.Model):
    """
    Product-specific details for product_type="medical" (health).
    Add fields here as your medical product flow evolves.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "medical_details"


class Lead(models.Model):
    STATUS_CHOICES = [
        ('NEW', 'New'),
        ('CONTACTED', 'Contacted'),
        ('QUALIFIED', 'Qualified'),
        ('LOST', 'Lost'),
    ]
    STAGE_CHOICES = [
        ("new_lead", "New Lead"),
        ("assigned", "Assigned"),
        ("non_contactable_1", "Non Contactable 1"),
        ("non_contactable_2", "Non Contactable 2"),
        ("non_contactable_3", "Non Contactable 3"),
        ("contactable", "Contactable"),
        ("requirement_gathering", "Requirement Gathering"),
        ("sales_qualified_lead", "Sales Qualified Lead"),
    ]
    PEP_STATUS_CHOICES = [
        ("yes", "Yes"),
        ("no", "No"),
    ]
    # Backend choices used by the frontend Create Lead screen.
    PREFERRED_CONTACT_METHODS = [
        ("whatsapp", "WhatsApp"),
        ("email", "Email"),
        ("call", "Call"),
    ]

    # Lead source (how the lead came in). Kept backward-compatible with older values.
    SOURCE_CHOICES = [
        ("lead_source", "Lead Source"),
        ("website", "Website"),
        ("referral", "Referral"),
        # legacy
        ("agent", "Agent"),
        ("direct", "Direct"),
    ]
    PRODUCT_TYPE_CHOICES = [
        ("general", "General"),
        ("motor", "Motor"),
        ("medical", "Medical"),
    ]
    INSURANCE_TYPE = [
        ("New Vehicle Registration", "New Vehicle Registration"),
        ("Change Vehicle Ownership", "Change Vehicle Ownership"),
        ("Vehicle Renewal", "Vehicle Renewal"),
        ("Import Vehicle", "Import Vehicle"),
        ("Export Certificate", "Export Certificate"),
        ("Update Registration Information", "Update Registration Information"),
        ("Issue Trade Plate", "Issue Trade Plate"),
        ("Renewal Trade Plate", "Renewal Trade Plate"),
        (
            "Vehicle Renewal with Change Number",
            "Vehicle Renewal with Change Number",
        ),
    ]

    SUB_TYPE_CHOICES = [
        ("comprehensive_agency", "Comprehensive - Agency"),
        ("comprehensive_non_agency", "Comprehensive - Non Agency"),
        ("third_party", "Third Party"),
    ]
    
    name = models.CharField(max_length=100)
    address = models.TextField(blank=True, null=True)
    occupation = models.CharField(max_length=150, blank=True, null=True)
    mobile_number = models.CharField(max_length=20, blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(unique=True)
    product_type = models.CharField(
        max_length=100, choices=PRODUCT_TYPE_CHOICES, blank=True, null=True
    )
    # NOTE: This field is used as preferred contact method in the current UI.
    delivery_channel = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        choices=PREFERRED_CONTACT_METHODS,
        verbose_name="Preferred Contact Method",
    )
    # insurance_type moved to motor_details (deals.Deal)
    is_pep = models.CharField(max_length=100, default=False, choices=PEP_STATUS_CHOICES, verbose_name="PEP Status")
    responsible = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name="assigned_leads")
    stage = models.CharField(max_length=100,default='Assigned',choices=STAGE_CHOICES, help_text="Current pipeline stage")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creation Date")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Modified")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='NEW')
    is_favorite = models.BooleanField(default=False)
    progress_score = models.IntegerField(default=0)
    notes = models.TextField(blank=True, null=True)
    source = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        choices=SOURCE_CHOICES,
        verbose_name="Lead Source",
    )
    # sub_type moved to motor_details (deals.Deal)

    # Product-specific details pointer (motor_details for product_type="motor").
    # Stored as `motor_product_id` column in `leads_lead`.
    motor_product = models.ForeignKey(
        "deals.Deal",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="motor_leads",
        db_column="motor_product_id",
    )

    # Product-specific table pointers for other product types.
    general_product = models.OneToOneField(
        "leads.GeneralDetails",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lead",
        db_column="general_product_id",
    )
    medical_product = models.OneToOneField(
        "leads.MedicalDetails",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lead",
        db_column="medical_product_id",
    )

    class Meta:
        verbose_name = "Lead"
        verbose_name_plural = "Leads"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name}"


class LeadActivity(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE)

    activity_type = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    subject = models.CharField(max_length=255, blank=True, null=True)

    timestamp = models.DateTimeField(auto_now_add=True)
    user_icon = models.URLField(blank=True, null=True)
    
    
