from django.shortcuts import render, get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import RegisterSerializer

# Create your views here.
from rest_framework.response import Response
from rest_framework.decorators import api_view

@api_view(['GET'])
def test_api(request):
    return Response({"message":"API working"})

from rest_framework.permissions import AllowAny

@api_view(['POST'])
@permission_classes([AllowAny]) 
def register_user(request):
    print("working")
    serializer = RegisterSerializer(data=request.data)
    print("working 2")
    if serializer.is_valid():
        print("working 3")
        serializer.save()
        return Response({
            "message": "User registered successfully",
            "data": serializer.data
        }, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



@api_view(['POST'])
@permission_classes([AllowAny]) 
def login_user(request):
    email = request.data.get('email')
    password = request.data.get('password')

    #using your EmailBackend
    user = authenticate(username=email, password=password)

    if user is not None:
        refresh = RefreshToken.for_user(user)

        return Response({
            "message": "Login successful",
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        })

    return Response({
        "error": "Invalid credentials"
    }, status=status.HTTP_401_UNAUTHORIZED)
    


from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes

@api_view(['POST'])
@permission_classes([IsAuthenticated])   
def logout_user(request):
    try:
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response({"error": "Refresh token required"}, status=status.HTTP_400_BAD_REQUEST)

        token = RefreshToken(refresh_token)
        token.blacklist()
        return Response({"message": "Logout successful"})
    except Exception as e:
        return Response({"error": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST)
    


@api_view(['GET'])
@permission_classes([IsAuthenticated])  #Protected
def protected_view(request):
    return Response({
        "message": "Access granted",
        "user": request.user.username
    })

from .permissions import IsAdminUser
from .serializers import UserSerializer
from django.contrib.auth.models import User


@api_view(['PUT'])
@permission_classes([IsAuthenticated, IsAdminUser])   # Only admin can access
def update_user_role(request, user_id):
    user = get_object_or_404(User, id=user_id)
    
    serializer = UserSerializer(user, data=request.data, partial=True, context={'request': request})
    
    if serializer.is_valid():
        serializer.save()
        return Response({
            "message": "User updated successfully",
            "data": serializer.data
        })
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

from .permissions import IsManagerUser

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsManagerUser])
def manager_dashboard(request):
    return Response({
        "message": "Manager access granted"
    })

from .models import Role
from rest_framework.permissions import IsAuthenticated

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_roles(request):
    roles = Role.objects.all()
    data = [{"id": r.id, "name": r.name} for r in roles]

    return Response({"roles": data})



from django.utils.timezone import now, timedelta
from django.db.models import Count, Sum
from rest_framework.views import APIView
from rest_framework.response import Response

# from .models import Renewal
from leads.models import Lead
from deals.models import Deals
from Quote.models import QuoteRequest
from Task.models import Task
from invoice.models import Transaction



class DashboardStatsView(APIView):

    def get(self, request):
        days = int(request.GET.get("days", 7))  # 7 / 30 / 90 / 180
        start_date = now() - timedelta(days=days)

        active_leads = Lead.objects.filter(created_at__gte=start_date).count()

        active_deals = Deals.objects.filter(status="active").count()

        pending_quotes = QuoteRequest.objects.filter(status="pending").count()

        pending_tasks = Task.objects.filter(status="pending").count()

        policies_issued = Transaction.objects.filter(invoice_date__isnull=False).count()

        revenue = Transaction.objects.filter(invoice_date__gte=start_date).aggregate(total=Sum("total_premium"))["total"] or 0

        pending_renewals = Transaction.objects.filter(policy_end_date__lte=now().date() + timedelta(days=30),policy_end_date__gte=now().date()).count()

        total_leads = Lead.objects.count()
        total_deals = Deals.objects.filter(status="closed").count()

        conversion_ratio = (
            f"{round(total_deals / total_leads, 2)}:1"
            if total_leads > 0 else "0:1"
        )

        data = {
            "active_leads": active_leads,
            "active_deals": active_deals,
            "pending_quotations": pending_quotes,
            "pending_tasks": pending_tasks,
            "policies_issued": policies_issued,
            "conversion_ratio": conversion_ratio,
            "revenue": revenue,
            "pending_renewals": pending_renewals,
        }

        return Response(data)




from django.db.models import Sum
from django.db.models.functions import TruncMonth
from rest_framework.views import APIView
from rest_framework.response import Response

from invoice.models import Transaction


class SalesTrendView(APIView):
    def get(self, request):

        data = (
            Transaction.objects
            .annotate(month=TruncMonth("invoice_date"))
            .values("month", "policy_type")
            .annotate(total=Sum("total_premium"))
            .order_by("month")
        )

        result = {}

        for item in data:
            month = item["month"].strftime("%b")
            policy = item["policy_type"]
            total = float(item["total"])

            if month not in result:
                result[month] = {}

            result[month][policy] = total

        return Response(result)
    
class ProductMixView(APIView):
    def get(self, request):

        data = (
            Transaction.objects
            .values("policy_type")
            .annotate(total=Sum("total_premium"))
        )

        total_sum = sum(item["total"] for item in data)

        result = []

        for item in data:
            percentage = (item["total"] / total_sum) * 100 if total_sum else 0

            result.append({
                "name": item["policy_type"],
                "value": round(percentage, 2)
            })

        return Response(result)
    
class RevenueTrendView(APIView):
    def get(self, request):

        data = (
            Transaction.objects
            .annotate(month=TruncMonth("invoice_date"))
            .values("month")
            .annotate(total=Sum("total_premium"))
            .order_by("month")
        )

        result = [
            {
                "month": item["month"].strftime("%b"),
                "revenue": float(item["total"])
            }
            for item in data
        ]

        return Response(result)
    

from django.db.models import Count

class ConversionFunnelView(APIView):
    def get(self, request):

        total_invoices = Transaction.objects.count()
        total_transactions = Transaction.objects.count()

        return Response({
            "invoices": total_invoices,
            "converted": total_transactions
        })