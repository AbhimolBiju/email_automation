from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail

from .models import Deal

@receiver(post_save, sender=Deal)
def send_customer_welcome_email(sender,instance,created,**kwargs):

    if not created:
        return
    
    #ensure deal is lead
    if not instance.lead:
        print("Deal has no linked deal.")
        return
    
    customer_email = instance.lead.email

    if not customer_email:
        print("Customer email not found.")
        return
    
    customer_name = instance.lead.name
    print(f"Sending Welcome email to : {customer_email}")

    try:
        send_mail(subject = "Welcome to Promise Insurance Services!",
                  message = f"""
                  Dear {customer_name},

Thank you for choosing Promise Insurance Services.

We are pleased to inform you that your request has been successfully processed, and our team has started handling your case.

Our representative will stay in touch with you regarding the next steps and any required updates.

If you have any questions, please feel free to contact us.

Best Regards,
Promise Insurance Services
""",
        from_email=None,
        recipient_list = [customer_email],
        fail_silently=False,
        )

        print(f"Welcome email sent to : {customer_email}")

    except Exception as e:
        print(f"Failed to send welcome email: {str(e)}")