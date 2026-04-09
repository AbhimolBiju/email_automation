from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class Task(models.Model):
    # Status and Priority Choices
    STATUS_CHOICES = [
        ('Todo', 'Todo'),
        ('In Progress', 'In Progress'),
        ('Done', 'Done'),
    ]
    
    PRIORITY_CHOICES = [
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
    ]

    # Primary Key and Basic Info
    title = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)

    # Foreign Key to User
    assigned_to = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='tasks',
        db_column='assigned_to_id'
    )

    # Generic Foreign Key Setup
    # This allows the task to point to any model (Policy, Lead, etc.)
    content_type = models.ForeignKey(
        ContentType, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    # Date and Status Fields
    due_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='Todo'
    )
    priority = models.CharField(
        max_length=10, 
        choices=PRIORITY_CHOICES, 
        default='Medium'
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'task'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.status}"
