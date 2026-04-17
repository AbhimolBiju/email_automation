from django.db import models

# Create your models here.
from django.db import models

# Create your models here.
class Invoice(models.Model):

    CUSTOMER_TYPE = (
        ('INDIVIDUAL', 'Individual'),
        ('COOPERATIVE', 'Cooperative'),
    )

    customer_type = models.CharField(max_length=20, choices=CUSTOMER_TYPE)

    # Common Fields
    producer = models.CharField(max_length=100, blank=True, null=True)
    main_customer = models.CharField(max_length=100, blank=True, null=True)
    creation_date = models.DateTimeField(auto_now_add=True)
    delivery_channel = models.CharField(max_length=100, blank=True, null=True)
    pep = models.BooleanField(default=False)
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "invoices"

    def __str__(self):
        return f"Invoice {self.id}"
class IndividualCustomer(models.Model):

    invoice = models.OneToOneField(
        Invoice,
        on_delete=models.CASCADE,
        related_name="individual"
    )
    
    title = models.CharField(max_length=10, blank=True, null=True)
    name = models.CharField(max_length=100)
    address = models.TextField()
    occupation = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField()
    mobile_number = models.CharField(max_length=20)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    gender = models.CharField(max_length=10, blank=True, null=True)
    dob = models.DateField(blank=True, null=True)
    emirates_id = models.CharField(max_length=50, blank=True, null=True)
    id_expiry_date = models.DateField(blank=True, null=True)
    nationality = models.CharField(max_length=50, blank=True, null=True)
    resident = models.BooleanField(default=False)

    class Meta:
        db_table = "individual_customers"

    def __str__(self):
        return self.name
    
class CooperativeCustomer(models.Model):
    invoice = models.OneToOneField(
        Invoice,
        on_delete=models.CASCADE,
        related_name="cooperative"
    )
    licence_type = models.CharField(max_length=100)
    company_name = models.CharField(max_length=150)
    trade_licence_id = models.CharField(max_length=100)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20)
    address = models.TextField()
    po_box = models.CharField(max_length=50, blank=True, null=True)
    contact_person = models.CharField(max_length=100)
    first_business_date = models.DateField(blank=True, null=True)
    insured_name = models.CharField(max_length=150, blank=True, null=True)
    resident = models.BooleanField(default=False)
    id_expiry_date = models.DateField(blank=True, null=True)
    nationality = models.CharField(max_length=50, blank=True, null=True)
    date_of_incorporation = models.DateField(blank=True, null=True)
    company_activity = models.TextField(blank=True, null=True)
    aml_trace = models.BooleanField(default=False)

    class Meta:
        db_table = "cooperative_customers"

    def __str__(self):
        return self.company_name

class Transaction(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="transactions")

    customer = models.CharField(max_length=100)
    direct_payment = models.BooleanField(default=False)
    insurer_name = models.CharField(max_length=150)

    invoice_date = models.DateField()
    policy_start_date = models.DateField()
    policy_end_date = models.DateField()

    premium_currency = models.CharField(max_length=10)
    amount_currency = models.CharField(max_length=10)

    branch = models.CharField(max_length=100)
    center = models.CharField(max_length=100)

    policy_type = models.CharField(max_length=100)
    policy_cover = models.CharField(max_length=100)
    reference_number = models.CharField(max_length=100)

    net_premium = models.DecimalField(max_digits=12, decimal_places=2)
    charges = models.DecimalField(max_digits=12, decimal_places=2)
    total_premium = models.DecimalField(max_digits=12, decimal_places=2)
    vat_amount = models.DecimalField(max_digits=12, decimal_places=2)
    net_due = models.DecimalField(max_digits=12, decimal_places=2)

    commission_percent = models.DecimalField(max_digits=5, decimal_places=2)
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2)

    insurer_reference = models.CharField(max_length=100)
    policy_number = models.CharField(max_length=100)
    tax_invoice_number = models.CharField(max_length=100)
    commission_invoice_number = models.CharField(max_length=100)

    due_date = models.DateField()
    
class Attachment(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="attachments")

    eid = models.FileField(upload_to="documents/", blank=True, null=True)
    passport = models.FileField(upload_to="documents/", blank=True, null=True)
    visa = models.FileField(upload_to="documents/", blank=True, null=True)
    policy_documents = models.FileField(upload_to="documents/", blank=True, null=True)
    policy_schedule = models.FileField(upload_to="documents/", blank=True, null=True)
    credit_note = models.FileField(upload_to="documents/", blank=True, null=True)
    debit_note = models.FileField(upload_to="documents/", blank=True, null=True)
    other_documents = models.FileField(upload_to="documents/", blank=True, null=True)

    system_generated_1 = models.BooleanField(default=False)
    system_generated_2 = models.BooleanField(default=False)
    system_generated_3 = models.BooleanField(default=False)

class StatusOverview(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="status_logs")

    status = models.CharField(max_length=100)
    date = models.DateTimeField(auto_now_add=True)
    pending_at = models.CharField(max_length=100)
    assigned_user = models.CharField(max_length=100)



class Reconciliation(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="reconciliations")

    rec_id = models.CharField(max_length=20, unique=True)

    policy_number = models.CharField(max_length=100)
    customer_name = models.CharField(max_length=100)

    billed_amount = models.DecimalField(max_digits=12, decimal_places=2)
    insurer_amount = models.DecimalField(max_digits=12, decimal_places=2)

    difference = models.DecimalField(max_digits=12, decimal_places=2)

    due_date = models.DateField()

    STATUS_CHOICES = (
        ('matched', 'Matched'),
        ('mismatch', 'Mismatch'),
        ('partial', 'Partial Match'),
        ('resolved', 'Resolved'),
        ('escalated', 'Escalated'),
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='mismatch')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "reconciliations"

    def __str__(self):
        return self.rec_id