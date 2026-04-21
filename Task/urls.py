from django.urls import path

from leads.views import lead_details,lead_list

from .views import create_task,list_task,completed_tasks
from . import views  # Assuming your function is in views.py

urlpatterns = [
    # Workflow Statistics API
    path('api/v1/workflow/stats', views.get_workflow_stats,name='workflow-stats'),
    path("<int:lead_id>/tasks/",create_task),
    path("export/",list_task),
    path("tasks/completed/",completed_tasks),
    path('<int:lead_id>/', lead_details),
   
    path('exports/',lead_list),

]