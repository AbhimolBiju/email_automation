from rest_framework import serializers
from .models import Invoice, IndividualCustomer

# 🔹 Individual Serializer
class IndividualCustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = IndividualCustomer
        exclude = ("invoice",)


# 🔹 Invoice Serializer (Main)
class InvoiceSerializer(serializers.ModelSerializer):

    individual = IndividualCustomerSerializer(required=False)

    class Meta:
        model = Invoice
        fields = [
            "id",
            "customer_type",
            "producer",
            "main_customer",
            "delivery_channel",
            "pep",
            "remarks",
            "individual",
        ]

    def create(self, validated_data):
        individual_data = validated_data.pop("individual", None)

        # ✅ Create Invoice
        invoice = Invoice.objects.create(**validated_data)

        # ✅ Create Individual (from form left side)
        if individual_data:
            IndividualCustomer.objects.create(
                invoice=invoice,
                **individual_data
            )

        return invoice
    
# class InvoiceListSerializer(serializers.ModelSerializer):

#     invoice_id = serializers.SerializerMethodField()
#     policy_number = serializers.SerializerMethodField()
#     customer_name = serializers.SerializerMethodField()
#     premium = serializers.SerializerMethodField()
#     issue_date = serializers.SerializerMethodField()
#     due_date = serializers.SerializerMethodField()
#     status = serializers.SerializerMethodField()
#     available_actions = serializers.SerializerMethodField()

#     class Meta:
#         model = Invoice
#         fields = [
#             "invoice_id",
#             "policy_number",
#             "customer_name",
#             "premium",
#             "issue_date",
#             "due_date",
#             "status",
#             "available_actions",
#         ]

#     def get_invoice_id(self, obj):
#         return f"INV-{obj.id:03d}"

#     def get_policy_number(self, obj):
#         tx = obj.transactions.first()
#         return tx.policy_number if tx else ""

#     def get_customer_name(self, obj):
#         try:
#             return obj.individual.name
#         except:
#             try:
#                 return obj.cooperative.company_name
#             except:
#                 return ""

#     def get_premium(self, obj):
#         tx = obj.transactions.first()
#         if tx:
#             return {
#                 "currency": tx.premium_currency,
#                 "amount": tx.total_premium
#             }
#         return {"currency": "", "amount": 0}

#     def get_issue_date(self, obj):
#         tx = obj.transactions.first()
#         return tx.invoice_date if tx else None

#     def get_due_date(self, obj):
#         tx = obj.transactions.first()
#         return tx.due_date if tx else None

#     def get_status(self, obj):
#         status_obj = obj.status_logs.last()
#         return status_obj.status.lower() if status_obj else "pending"

#     def get_available_actions(self, obj):
#         status = self.get_status(obj)

#         if status == "paid":
#             return ["download"]
#         elif status in ["pending", "overdue"]:
#             return ["download", "send_reminder"]

#         return []



class InvoiceListSerializer(serializers.ModelSerializer):

    # 🔹 Invoice
    invoice_id = serializers.SerializerMethodField()
    customer_type = serializers.CharField()
    producer = serializers.CharField()
    main_customer = serializers.CharField()
    delivery_channel = serializers.CharField()
    pep = serializers.BooleanField()
    remarks = serializers.CharField()

    # 🔹 Customer
    customer_name = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    mobile_number = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()
    nationality = serializers.SerializerMethodField()

    # 🔹 Transaction
    policy_number = serializers.SerializerMethodField()
    insurer_name = serializers.SerializerMethodField()
    premium = serializers.SerializerMethodField()
    issue_date = serializers.SerializerMethodField()
    due_date = serializers.SerializerMethodField()
    branch = serializers.SerializerMethodField()
    policy_type = serializers.SerializerMethodField()

    # 🔹 Status
    status = serializers.SerializerMethodField()
    available_actions = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            "invoice_id",
            "customer_type",
            "producer",
            "main_customer",
            "delivery_channel",
            "pep",
            "remarks",

            "customer_name",
            "email",
            "mobile_number",
            "address",
            "nationality",

            "policy_number",
            "insurer_name",
            "premium",
            "issue_date",
            "due_date",
            "branch",
            "policy_type",

            "status",
            "available_actions",
        ]

    # ✅ Invoice ID
    def get_invoice_id(self, obj):
        return f"INV-{obj.id:03d}"

    # ================= CUSTOMER =================

    def get_customer_name(self, obj):
        if hasattr(obj, 'individual') and obj.individual:
            return obj.individual.name
        if hasattr(obj, 'cooperative') and obj.cooperative:
            return obj.cooperative.company_name
        return None

    def get_email(self, obj):
        if hasattr(obj, 'individual') and obj.individual:
            return obj.individual.email
        if hasattr(obj, 'cooperative') and obj.cooperative:
            return obj.cooperative.email
        return None

    def get_mobile_number(self, obj):
        if hasattr(obj, 'individual') and obj.individual:
            return obj.individual.mobile_number
        if hasattr(obj, 'cooperative') and obj.cooperative:
            return obj.cooperative.phone_number
        return None

    def get_address(self, obj):
        if hasattr(obj, 'individual') and obj.individual:
            return obj.individual.address
        if hasattr(obj, 'cooperative') and obj.cooperative:
            return obj.cooperative.address
        return None

    def get_nationality(self, obj):
        if hasattr(obj, 'individual') and obj.individual:
            return obj.individual.nationality
        if hasattr(obj, 'cooperative') and obj.cooperative:
            return obj.cooperative.nationality
        return None

    # ================= TRANSACTION =================

    def get_policy_number(self, obj):
        tx = obj.transactions.first()
        return tx.policy_number if tx else None

    def get_insurer_name(self, obj):
        tx = obj.transactions.first()
        return tx.insurer_name if tx else None

    def get_premium(self, obj):
        tx = obj.transactions.first()
        if tx:
            return {
                "currency": tx.premium_currency,
                "amount": float(tx.total_premium)
            }
        return None

    def get_issue_date(self, obj):
        tx = obj.transactions.first()
        return tx.invoice_date if tx else None

    def get_due_date(self, obj):
        tx = obj.transactions.first()
        return tx.due_date if tx else None

    def get_branch(self, obj):
        tx = obj.transactions.first()
        return tx.branch if tx else None

    def get_policy_type(self, obj):
        tx = obj.transactions.first()
        return tx.policy_type if tx else None

    # ================= STATUS =================

    def get_status(self, obj):
        status_obj = obj.status_logs.order_by('-date').first()
        return status_obj.status.lower() if status_obj else "pending"

    def get_available_actions(self, obj):
        status = self.get_status(obj)

        if status == "paid":
            return ["download"]
        elif status in ["pending", "overdue"]:
            return ["download", "send_reminder"]

        return []
    
class BillingSummarySerializer(serializers.Serializer):
    total_revenue = serializers.DictField()
    paid_count = serializers.IntegerField()
    pending_count = serializers.IntegerField()
    overdue_count = serializers.IntegerField()


class ImportStatementSerializer(serializers.Serializer):
    file = serializers.FileField()