from django.db import models

# Create your models here.

class Document(models.Model):
    file = models.FileField(upload_to='documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)



class OCRDocument(models.Model):

    STATUS_CHOICES = [
        ('VERIFIED', 'Verified'),
        ('PENDING', 'Pending'),
        ('REJECTED', 'Rejected'),
        ('LOW_CONFIDENCE', 'Low Confidence'),
    ]

    document_id = models.CharField(max_length=20, unique=True)
    lead_id = models.CharField(max_length=20)
    first_name = models.CharField(max_length=100)
    document_type = models.CharField(max_length=100)
    product = models.CharField(max_length=100)
    confidence_score = models.IntegerField(default=0)
    upload_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)

    def __str__(self):
        return self.document_id