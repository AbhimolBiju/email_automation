from django.db import models

# Create your models here.
from django.contrib.auth.models import User
from django.db import models

class CustomUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    def __str__(self):
        return self.user.email
    
     
#Role Model 
class Role(models.Model):
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

    name = models.CharField(max_length=20, choices=ROLE_CHOICES, unique=True)

    def __str__(self):
        return self.get_name_display()
    
#Profile model
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    name = models.CharField(max_length=100)
    bio = models.TextField(blank=True, null=True)
    profile_pic = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True)


    def __str__(self):
        return self.user.username
    
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        from .models import Role  # import here to avoid circular import

        default_role, _ = Role.objects.get_or_create(name='customers')

        Profile.objects.create(
            user=instance,
            role=default_role
        )

@receiver(post_save, sender=User)
def save_profile(sender, instance, **kwargs):
    instance.profile.save()