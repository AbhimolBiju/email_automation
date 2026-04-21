from django.shortcuts import render

# Create your views here.
from datetime import timedelta
from turtle import pd

from rest_framework.decorators import api_view
from rest_framework.response import Response

from invoice.models import Invoice
from invoice.serializer import BillingSummarySerializer, ImportStatementSerializer, InvoiceListSerializer, InvoiceSerializer
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.timezone import now

from invoice.serializer import InvoiceSerializer

@api_view(['POST'])
def create_invoice(request):
    print("DATA:", request.data)
    serializer = InvoiceSerializer(data=request.data)

    if serializer.is_valid():
        invoice = serializer.save()
        return Response({
            "message": "Invoice Created Successfully ",
            "invoice_id": invoice.id
        })
    print("ERROR:", serializer.errors)

    return Response(serializer.errors, status=400)



# @api_view(['GET'])
# def invoice_list(request):
#     print("QUERY PARAMS:", request.GET)  # Debugging line to check incoming query params
#     # 🔹 Query params
#     status_filter = request.GET.get('status')   # paid / pending / overdue
#     search = request.GET.get('search')          # search term
#     page = int(request.GET.get('page', 1))

#     # 🔹 Base queryset
#     invoices = Invoice.objects.all().order_by('-id')
#     print("Initial Invoices Count:", invoices.count())  # Debugging line to check initial count
#     # 🔍 SEARCH (name + policy number)
#     if search:
#         invoices = invoices.filter(
#             Q(individual__name__icontains=search) |
#             Q(cooperative__company_name__icontains=search) |
#             Q(transactions__policy_number__icontains=search)
#         ).distinct()

#     # 🔎 STATUS FILTER
#     if status_filter:
#         filtered_invoices = []

#         for inv in invoices:
#             status_obj = inv.status_logs.last()

#             if status_obj and status_obj.status.lower() == status_filter.lower():
#                 filtered_invoices.append(inv)

#         invoices = filtered_invoices

#     paginator = Paginator(invoices, 10)
#     page_obj = paginator.get_page(page)

#     serializer = InvoiceListSerializer(page_obj, many=True)

#     return Response({
#         "results_found": paginator.count,
#         "data": serializer.data
#     })

@api_view(['GET'])
def invoice_list(request):

    status_filter = request.GET.get('status')
    search = request.GET.get('search')
    page = int(request.GET.get('page', 1))

    invoices = Invoice.objects.all().order_by('-id')

  
    if search:
        invoices = invoices.filter(
            Q(individual__name__icontains=search) |
            Q(cooperative__company_name__icontains=search) |
            Q(transactions__policy_number__icontains=search)
        ).distinct()

  
    if status_filter:
        invoices = invoices.filter(
            status_logs__status__iexact=status_filter
        ).distinct()

  
    paginator = Paginator(invoices, 10)
    page_obj = paginator.get_page(page)

    serializer = InvoiceListSerializer(page_obj, many=True)

    #  FILTER ONLY REQUIRED TABLE FIELDS
    table_data = []
    for item in serializer.data:
        table_data.append({
            "invoice_id": item["invoice_id"],
            "policy_number": item["policy_number"],
            "customer_name": item["customer_name"],
            "premium": item["premium"],
            "issue_date": item["issue_date"],
            "due_date": item["due_date"],
            "status": item["status"],
            "available_actions": item["available_actions"],
        })

    return Response({
        "results_found": paginator.count,
        "data": table_data
    })


@api_view(['GET'])
def billing_summary(request):
    period = request.GET.get('period', 'this_year')

    today = now()

    # 🔹 Date filter
    if period == "7days":
        start_date = today - timedelta(days=7)
    elif period == "30days":
        start_date = today - timedelta(days=30)
    elif period == "90days":
        start_date = today - timedelta(days=90)
    else:
        start_date = today.replace(month=1, day=1)

    invoices = Invoice.objects.filter(creation_date__gte=start_date)

    total_revenue = 0
    paid_count = 0
    pending_count = 0
    overdue_count = 0

    for inv in invoices:
        tx = inv.transactions.first()
        status_obj = inv.status_logs.order_by('-date').first()

        if tx:
            total_revenue += float(tx.total_premium)

        status = status_obj.status.lower() if status_obj else "pending"

        if status == "paid":
            paid_count += 1
        elif status == "pending":
            pending_count += 1
        elif status == "overdue":
            overdue_count += 1

    # 🔹 Prepare data
    data = {
        "total_revenue": {
            "currency": "AED",
            "amount": total_revenue
        },
        "paid_count": paid_count,
        "pending_count": pending_count,
        "overdue_count": overdue_count
    }

    serializer = BillingSummarySerializer(data)

    return Response(serializer.data)

@api_view(['POST'])
def import_statement(request):
    serializer = ImportStatementSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    file = serializer.validated_data['file']

    try:
        # 🔹 Read file (CSV or Excel)
        if file.name.endswith('.csv'):
            df = pd.read_csv(file)
        elif file.name.endswith('.xlsx') or file.name.endswith('.xls'):
            df = pd.read_excel(file)
        else:
            return Response({"error": "Unsupported file format"}, status=400)

        # 🔹 Convert data to list (optional)
        data = df.to_dict(orient="records")

        # 🔹 Example: just return count
        return Response({
            "message": "File uploaded successfully",
            "total_records": len(data),
            "preview": data[:5]   # first 5 rows
        })

    except Exception as e:
        return Response({"error": str(e)}, status=500)