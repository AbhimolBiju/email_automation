from django.db import models
from django.conf import settings
# Create your models here.
from django.db import models
from django.conf import settings

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
    DELIVERY_CHANNEL_CHOICES = [
        ("agent", "Agent"),
        ("broker", "Broker"),
    ]
    PRODUCT_TYPE_CHOICES = [
        ("life", "Life"),
        ("health", "Health"),
        ("motor", "Motor"),
        ("travel", "Travel"),
        ("property", "Property"),
    ]
    
    name = models.CharField(max_length=100)
    address = models.TextField(blank=True, null=True)
    occupation = models.CharField(max_length=150, blank=True, null=True)
    mobile_number = models.CharField(max_length=20, blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(unique=True)
    product_type = models.CharField(max_length=100, choices=PRODUCT_TYPE_CHOICES,blank=True, null=True)
    delivery_channel = models.CharField(max_length=255,blank=True,null=True,choices=DELIVERY_CHANNEL_CHOICES, verbose_name="Lead Source")
    is_pep = models.CharField(default=False,choices=PEP_STATUS_CHOICES, verbose_name="PEP Status")
    responsible = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name="assigned_leads")
    stage = models.CharField(max_length=100,default='Assigned',choices=STAGE_CHOICES, help_text="Current pipeline stage")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creation Date")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Modified")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='NEW')
    is_favorite = models.BooleanField(default=False)
    progress_score = models.IntegerField(default=0)
    notes = models.TextField(blank=True, null=True)

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
    
    
