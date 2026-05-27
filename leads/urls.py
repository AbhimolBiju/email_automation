"""
URL configuration for crm_pro project.
"""

from django.urls import path
from .views import *

urlpatterns = [

    # ---------------------------------------------------
    # LEADS
    # ---------------------------------------------------

    # Create lead
    path("create/", create_lead, name="create"),

    # Lead list
    path("", lead_list, name="lead_list"),

    # Export leads
    path("export/", lead_list, name="export_leads"),

    # Assignable users
    path("assignable-users/", assignable_users),

    # Lead details
    path("<int:lead_id>/", lead_details),

    # Update lead status
    path("<int:lead_id>/status/", update_lead_status),

    # Update lead stage
    path("<int:lead_id>/stage/", update_lead_stage),

    # ---------------------------------------------------
    # ACTIVITIES
    # ---------------------------------------------------

    path("<int:lead_id>/activities/create/", create_activity),
    path("<int:lead_id>/activities/", lead_activities),

    # ---------------------------------------------------
    # FAVORITES
    # ---------------------------------------------------

    path(
        "<int:id>/favorite/",
        ToggleFavoriteView.as_view(),
        name="toggle-favorite"
    ),

    # ---------------------------------------------------
    # DASHBOARD / STATS
    # ---------------------------------------------------

    path(
        "status_view/",
        StatsView.as_view(),
        name="StatsView"
    ),

    # ---------------------------------------------------
    # NOTIFICATIONS
    # ---------------------------------------------------

    # Old activity feed notifications
    path("notifications/", notifications),

    # Real notification system
    path(
        "notifications/<int:id>/read/",
        mark_notification_read
    ),

    path(
        "user-notifications/",
        user_notifications
    ),

    path(
        "user-notifications/unread-count/",
        unread_notifications_count
    ),
]