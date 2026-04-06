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

    status = models.CharField(max_length=20, default='NEW')
    current_stage = models.IntegerField(default=1)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='NEW'
    )

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