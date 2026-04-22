from django.shortcuts import render, get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from .cookie_auth import clear_refresh_cookie, set_refresh_cookie, refresh_cookie_name
from .responses import success_response
from .serializers import RegisterStep1Serializer,RegisterStep2Serializer,UserProfileSerializer
from .models import CustomUser,User
# Create your views here.
from rest_framework.response import Response
from rest_framework.exceptions import NotFound, ValidationError, AuthenticationFailed

@api_view(['GET'])
@permission_classes([AllowAny])
def test_api(request):
    return success_response(message="API working", data={"status": "ok"})



@api_view(['POST'])
@permission_classes([AllowAny])
def register_step1(request):
    serializer = RegisterStep1Serializer(data=request.data)

    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data.copy()

    
    data['date_of_birth'] = data['date_of_birth'].isoformat()

    request.session['registration_data'] = data

    return success_response(
        message="Step 1 completed. Proceed to set password.",
        data=None,
        status_code=status.HTTP_200_OK,
    )




from datetime import date


@api_view(['POST'])
@permission_classes([AllowAny])
def register_step2(request):
    serializer = RegisterStep2Serializer(data=request.data)

    serializer.is_valid(raise_exception=True)
    reg_data = request.session.get('registration_data')
        
        
    if not reg_data:
        raise ValidationError({"registration": ["Session expired. Start again."]})
        
    reg_data['date_of_birth'] = date.fromisoformat(reg_data['date_of_birth'])

    # Create User
    user = User.objects.create_user(
        username=reg_data['email'],
        email=reg_data['email'],
        password=serializer.validated_data['password'],
        first_name=reg_data['first_name'],
        last_name=reg_data['last_name']
    )

    # Create CustomUser
    CustomUser.objects.create(
        user=user,
        mobile=reg_data['mobile'],
        date_of_birth=reg_data['date_of_birth'],
        gender=reg_data['gender']
    )

    # Clear session
    del request.session['registration_data']

    return success_response(
        message="Registration successful",
        data={"user_id": user.id},
        status_code=status.HTTP_201_CREATED,
    )


@api_view(['POST'])
@permission_classes([AllowAny]) 
def login_user(request):
    email = request.data.get('email')
    password = request.data.get('password')

    #using your EmailBackend
    user = authenticate(username=email, password=password)

    if user is not None:
        refresh = RefreshToken.for_user(user)
        access = str(refresh.access_token)
        refresh_str = str(refresh)

        response = success_response(
            message="Login successful",
            data={
                "access": access,
                "user": {
                    "id": user.id,
                    "email": getattr(user, "email", None),
                    "username": user.username,
                },
            },
            status_code=status.HTTP_200_OK,
        )
        # Refresh token only via HttpOnly cookie (not in JSON).
        set_refresh_cookie(response, refresh_str)
        return response

    raise AuthenticationFailed("Unauthorized")




@api_view(['POST'])
@permission_classes([AllowAny])
def logout_user(request):
    """
    Blacklist refresh token (from HttpOnly cookie or legacy JSON body) and clear cookie.
    AllowAny so a client can log out even if the access token is already expired.
    """
    refresh_token = request.COOKIES.get(refresh_cookie_name()) or request.data.get(
        "refresh"
    )
    response = success_response(message="Logout successful", data=None)
    if refresh_token:
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            pass
    clear_refresh_cookie(response)
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])  #Protected
def protected_view(request):
    return success_response(
        message="Access granted",
        data={"user": request.user.username},
    )




@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    try:
        profile = request.user.user_profile
    except CustomUser.DoesNotExist:
        raise NotFound("Profile not found")

    if request.method == 'GET':
        serializer = UserProfileSerializer(profile)
        return success_response(message="Profile fetched successfully", data=serializer.data)

    if request.method in ['PUT', 'PATCH']:
        serializer = UserProfileSerializer(
            profile,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            serializer.save()
            return success_response(message="Profile updated successfully", data=serializer.data)

        serializer.is_valid(raise_exception=True)




from django.utils.timezone import now, timedelta
from django.db.models import Count, Sum
from rest_framework.views import APIView
from rest_framework.response import Response

# from .models import Renewal
from leads.models import Lead
from deals.models import Deal
from Quote.models import QuoteRequest
from Task.models import Task
from invoice.models import Transaction



class DashboardStatsView(APIView):

    def get(self, request):
        days = int(request.GET.get("days", 7))  # 7 / 30 / 90 / 180
        start_date = now() - timedelta(days=days)
        prev_start_date = start_date - timedelta(days=days)

        active_leads = Lead.objects.filter(created_at__gte=start_date).count()
        prev_active_leads = Lead.objects.filter(
            created_at__gte=prev_start_date, created_at__lt=start_date
        ).count()

        active_deals = Deal.objects.filter(stage_id__lt=12).count()
        prev_active_deals = Deal.objects.filter(stage_id__lt=12, created_at__gte=prev_start_date, created_at__lt=start_date).count()

        pending_quotes = QuoteRequest.objects.filter(status="pending").count()
        prev_pending_quotes = QuoteRequest.objects.filter(status="pending", created_at__gte=prev_start_date, created_at__lt=start_date).count()

        pending_tasks = Task.objects.filter(status="pending").count()
        prev_pending_tasks = Task.objects.filter(status="pending", created_at__gte=prev_start_date, created_at__lt=start_date).count()

        policies_issued = Transaction.objects.filter(invoice_date__isnull=False).count()
        prev_policies_issued = Transaction.objects.filter(invoice_date__gte=prev_start_date, invoice_date__lt=start_date).count()

        revenue = Transaction.objects.filter(invoice_date__gte=start_date).aggregate(total=Sum("total_premium"))["total"] or 0
        prev_revenue = Transaction.objects.filter(invoice_date__gte=prev_start_date, invoice_date__lt=start_date).aggregate(total=Sum("total_premium"))["total"] or 0

        pending_renewals = Transaction.objects.filter(policy_end_date__lte=now().date() + timedelta(days=30),policy_end_date__gte=now().date()).count()
        prev_pending_renewals = Transaction.objects.filter(policy_end_date__lte=(now().date() - timedelta(days=days)), policy_end_date__gte=(now().date() - timedelta(days=days+30))).count()

        total_leads = Lead.objects.count()
        total_deals = Deal.objects.filter(stage_id__gte=12).count()
        



        conversion_ratio = (
            f"{round(total_deals / total_leads, 2)}:1"
            if total_leads > 0 else "0:1"
        )

        def pct(curr: float, prev: float) -> int:
            if prev == 0:
                return 0 if curr == 0 else 100
            return int(round(((curr - prev) / prev) * 100))

        label = f"vs last {days} days"

        data = {
            "cards": [
                {"id": "1", "title": "Active Leads", "value": str(active_leads), "trend": pct(active_leads, prev_active_leads), "label": label},
                {"id": "2", "title": "Active Deals", "value": str(active_deals), "trend": pct(active_deals, prev_active_deals), "label": label},
                {"id": "3", "title": "Pending Quotations", "value": str(pending_quotes), "trend": pct(pending_quotes, prev_pending_quotes), "label": label},
                {"id": "4", "title": "Pending Tasks", "value": str(pending_tasks), "trend": pct(pending_tasks, prev_pending_tasks), "label": label},
                {"id": "5", "title": "Policies Issued", "value": str(policies_issued), "trend": pct(policies_issued, prev_policies_issued), "label": label},
                {"id": "6", "title": "Conversion Ratio", "value": conversion_ratio, "trend": 0, "label": label},
                {"id": "7", "title": "Revenue", "value": f"AED {round(float(revenue), 2)}", "trend": pct(float(revenue), float(prev_revenue)), "label": label},
                {"id": "8", "title": "Pending Renewals", "value": str(pending_renewals), "trend": pct(pending_renewals, prev_pending_renewals), "label": label},
            ],
            "days": days,
        }

        return success_response(message="Dashboard stats fetched successfully", data=data)




from django.db.models import Sum
from django.db.models.functions import TruncMonth
from rest_framework.views import APIView
from api.responses import success_response

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

        return success_response(message="Sales trend fetched successfully", data=result)
    
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

        return success_response(message="Product mix fetched successfully", data=result)
    
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

        return success_response(message="Revenue trend fetched successfully", data=result)
    

from django.db.models import Count

class ConversionFunnelView(APIView):
    def get(self, request):

        total_invoices = Transaction.objects.count()
        total_transactions = Transaction.objects.count()

        return success_response(
            message="Conversion funnel fetched successfully",
            data={"invoices": total_invoices, "converted": total_transactions},
        )
