from django.db import models

# Create your models here.
from django.contrib.auth.models import User
from django.db import models




class CustomUser(models.Model):
    
    ROLE_CHOICES = [
        ('superadmin', 'Superadmin'),
        ('general_manager', 'General manager'),
        ('operations_manager', 'Operations manager'),
        ('department_head','Department head'),
        ('underwriter','Underwriter'),
        ('sales_manager','Sales manager'),
        ('telecallers','Telecallers'),
        ('customers','Customers'),
        ('accounts','Accounts')
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='user_profile')
    mobile = models.CharField(max_length=15, null=True, unique=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=100, null=True)
    address = models.TextField(null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    zip_code = models.CharField(max_length=20, null=True, blank=True)
    country = models.CharField(max_length=100, null=True, blank=True)
    emirates_of_visa = models.CharField(max_length=100, null=True, blank=True)
    insurance_company = models.CharField(max_length=100, null=True, blank=True)
    currently_insured = models.BooleanField(default=False)
    salary_band = models.CharField(max_length=100, null=True, blank=True)
    profile_pic = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES,null=True, blank=True)

    def __str__(self):
        return self.user.email if self.user.email else str(self.user)
    
   