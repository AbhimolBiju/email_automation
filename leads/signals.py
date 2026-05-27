from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.core.mail import send_mail

from .models import Lead
from .models import LeadActivity
from .models import Notification


def _assignee_contact(user):
    return user.email or user.username


def _assignee_role(user):
    profile = getattr(user, "user_profile", None)
    return getattr(profile, "role", None)


@receiver(pre_save, sender=Lead)
def track_previous_responsible(sender, instance, **kwargs):

    if instance.pk:
        previous = Lead.objects.get(pk=instance.pk)
        instance._previous_responsible = previous.responsible
    else:
        instance._previous_responsible = None


@receiver(post_save, sender=Lead)
def send_assignment_notification(sender, instance, created, **kwargs):

    old_user = getattr(instance, "_previous_responsible", None)
    new_user = instance.responsible

    # Trigger only when responsible changes
    if old_user != new_user and new_user:
        assignee_email = _assignee_contact(new_user)
        assignee_role = _assignee_role(new_user)

        print(f"Lead assigned to: {assignee_email}")
        print(f"Assigned role: {assignee_role}")

        # Create frontend notification
        Notification.objects.create(
            user=new_user,
            lead=instance,
            title="New Lead Assigned",
            message=f"Lead {instance.name} has been assigned to you",
        )

        print(f"Notification created for: {assignee_email}")

        # Create CRM activity log
        LeadActivity.objects.create(
            lead=instance,
            activity_type="LEAD_ASSIGNED",
            subject="Lead Assigned",
            description=f"Lead assigned to {new_user.username}",
        )

        # Send email notification
        if new_user.email:
            send_mail(
                subject="New Lead Assigned",
                message=f"""
Hello {new_user.username},

A new lead has been assigned to you.

Lead Name: {instance.name}
Lead Email: {instance.email}
Lead Phone: {instance.mobile_number}

Please check CRM dashboard.
""",
                from_email=None,
                recipient_list=[new_user.email],
                fail_silently=True,
            )

            print(f"Email sent to: {new_user.email}")