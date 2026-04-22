from asyncio import Task

from django.shortcuts import render

# Create your views here.
from rest_framework.decorators import api_view
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from .models import  Task
# from Policy.models import Policy
from leads.models import Lead
from rest_framework import status,viewsets
from .serializers import LeadListSerializer, TaskSerializer, WorkflowStatsSerializer
from rest_framework.exceptions import ValidationError
from api.responses import success_response

@api_view(['GET'])
def get_workflow_stats(request):
    """
    API endpoint for the metric cards at the top of the workflow dashboard.
    """
    # 1. Handle Query Parameters
    period = request.query_params.get('period', '7days')
    
    # 2. Setup Time Filter Logic
    now = timezone.now()
    if period == '30days':
        start_date = now - timedelta(days=30)
    elif period == '90days':
        start_date = now - timedelta(days=90)
    elif period == 'this_year':
        start_date = now.replace(month=1, day=1, hour=0, minute=0)
    else:  # Default to 7days
        start_date = now - timedelta(days=7)

    # 3. Aggregate Data using the Policy Model
    # We group stages based on your dashboard's 7-step pipeline
    stats = Policy.objects.filter(created_at__gte=start_date).aggregate(
        total_tasks=Count('i_policy_id'),
        pending_customer=Count(
            'i_policy_id', 
            filter=Q(stage__in=['Leads', 'Documents'])
        ),
        pending_underwriter=Count(
            'i_policy_id', 
            filter=Q(stage__in=['Quotation', 'Acceptance'])
        ),
        completed_tasks=Count(
            'i_policy_id', 
            filter=Q(stage__in=['Billing', 'Claims', 'Completed'])
        )
    )

    # 4. Serialize and Respond
    serializer = WorkflowStatsSerializer(stats)
    return success_response(
        message="Workflow stats fetched successfully",
        data=serializer.data,
        status_code=status.HTTP_200_OK,
    )

@api_view(['POST'])
def create_task(request, lead_id=None):  # <--- accept lead_id
    data = request.data.copy()  # make mutable
    if lead_id:
        data['lead'] = lead_id  # attach lead_id to request data

    serializer = TaskSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return success_response(
        message="Task created successfully",
        data=serializer.data,
        status_code=status.HTTP_201_CREATED,
    )

@api_view(['GET'])
def list_task(request):
    # user_id = request.GET.get('assigned_to')

    # if user_id:
    #     tasks = Task.objects.filter(assigned_to=user_id)
    tasks = Task.objects.all()

    serializer = TaskSerializer(tasks, many=True)

    return success_response(
        message="Tasks fetched successfully",
        data=serializer.data,
        meta={"total": tasks.count()},
        status_code=status.HTTP_200_OK,
    )

@api_view(['GET'])
def completed_tasks(request):
    # filter only completed tasks
    tasks = Task.objects.filter(status='Done')

    serializer = TaskSerializer(tasks, many=True)

    return success_response(
        message="Completed tasks fetched successfully",
        data=serializer.data,
        meta={"total": tasks.count()},
        status_code=status.HTTP_200_OK,
    )
@api_view(['GET'])
def lead_list(request):
    leads = Lead.objects.all().order_by('-created_at')

    serializer = LeadListSerializer(leads, many=True)

    return success_response(
        message="Leads fetched successfully",
        data=serializer.data,
        meta={"total": leads.count()},
        status_code=status.HTTP_200_OK,
    )





