from django.db import models

# Create your models here.
from django.db import models

class Policy(models.Model):
    # --- Identification & Primary Key ---
    i_policy_id = models.IntegerField(primary_key=True)  # The link for other tables
    pol_no = models.IntegerField(null=True, blank=True)
    on_poi_no = models.IntegerField(null=True, blank=True)
    ion_poi_no = models.IntegerField(null=True, blank=True)
    
    # --- Status Flags ---
    open_pol = models.BooleanField(default=False)
    no_renewal = models.BooleanField(default=False)
    partial_refund_del = models.BooleanField(default=False)
    
    # --- Client & Policy Info ---
    name_1a = models.CharField(max_length=255, null=True, blank=True)
    address_1a = models.TextField(null=True, blank=True)
    cover_type = models.CharField(max_length=100, null=True, blank=True)
    ins_name = models.CharField(max_length=255, null=True, blank=True)
    ins_grp = models.CharField(max_length=100, null=True, blank=True)
    cust_grp = models.CharField(max_length=100, null=True, blank=True)
    
    # --- Dates ---
    to_date = models.DateTimeField(null=True, blank=True)
    exp_date = models.DateTimeField(null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    diff_date = models.DateTimeField(null=True, blank=True)
    self_billing_date = models.DateTimeField(null=True, blank=True)
    
    # --- Payment & Accounting ---
    mode_of_payment = models.IntegerField(null=True, blank=True)
    mode_of_payment_code = models.IntegerField(null=True, blank=True)
    pay_inst_years = models.IntegerField(null=True, blank=True)
    self_billing = models.CharField(max_length=100, null=True, blank=True)
    self_billing_no = models.IntegerField(null=True, blank=True)
    cti_amt = models.CharField(max_length=100, null=True, blank=True)
    
    # --- Metadata ---
    usr_name = models.CharField(max_length=100, null=True, blank=True)
    t_remark = models.TextField(null=True, blank=True)
    user_ref = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        db_table = 'policy'
        verbose_name_plural = "Policies"