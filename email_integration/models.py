
# Create your models here.
from django.db import models
from django.contrib.auth.models import User


class OutlookAccount(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    email = models.EmailField()
    access_token = models.TextField()
    refresh_token = models.TextField()
    expires_in = models.IntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email