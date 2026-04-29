from django.contrib import admin, messages

from .models import InsuranceInfo, InsuranceProvider, QuoteBatch, QuoteRequestLog, QuoteResult
from .services import health_check_provider


@admin.register(InsuranceInfo)
class InsuranceInfoAdmin(admin.ModelAdmin):
    list_display = ("id", "lead", "gender", "currently_insured")
    search_fields = ("lead__name", "lead__email", "emirates_id")


@admin.action(description="Enable selected providers")
def enable_providers(modeladmin, request, queryset):
    updated = queryset.update(is_active=True)
    modeladmin.message_user(request, f"Enabled {updated} provider(s).", level=messages.SUCCESS)


@admin.action(description="Disable selected providers")
def disable_providers(modeladmin, request, queryset):
    updated = queryset.update(is_active=False)
    modeladmin.message_user(request, f"Disabled {updated} provider(s).", level=messages.SUCCESS)


@admin.action(description="Test connection for selected providers")
def test_provider_connections(modeladmin, request, queryset):
    for provider in queryset:
        try:
            result = health_check_provider(provider)
            modeladmin.message_user(
                request,
                f"{provider.code}: health check passed ({result}).",
                level=messages.SUCCESS,
            )
        except Exception as exc:
            modeladmin.message_user(
                request,
                f"{provider.code}: health check failed ({exc}).",
                level=messages.ERROR,
            )


@admin.register(InsuranceProvider)
class InsuranceProviderAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "is_active",
        "priority",
        "timeout",
        "provider_class",
        "masked_api_key",
        "masked_password",
        "updated_at",
    )
    list_filter = ("is_active",)
    search_fields = ("name", "code", "provider_class")
    ordering = ("priority", "name")
    actions = (enable_providers, disable_providers, test_provider_connections)


@admin.register(QuoteRequestLog)
class QuoteRequestLogAdmin(admin.ModelAdmin):
    list_display = ("deal", "provider", "batch", "status", "latency_ms", "created_at")
    list_filter = ("status", "provider")
    search_fields = ("deal__id", "provider__code", "error_message")
    readonly_fields = (
        "deal",
        "provider",
        "request_payload",
        "response_payload",
        "status",
        "latency_ms",
        "error_message",
        "created_at",
    )


@admin.register(QuoteBatch)
class QuoteBatchAdmin(admin.ModelAdmin):
    list_display = ("reference_no", "deal", "lead", "best_provider", "best_total", "status", "requested_at")
    list_filter = ("status",)
    search_fields = ("reference_no", "deal__id", "lead__name", "lead__email")
    readonly_fields = (
        "reference_no",
        "deal",
        "lead",
        "triggered_by",
        "best_provider",
        "best_total",
        "status",
        "cache_expires_at",
        "requested_at",
        "updated_at",
    )


@admin.register(QuoteResult)
class QuoteResultAdmin(admin.ModelAdmin):
    list_display = ("batch", "provider", "plan_name", "total", "status", "ranking", "created_at")
    list_filter = ("provider", "currency", "status")
    search_fields = ("batch__reference_no", "deal__id", "provider__code", "plan_name")
    readonly_fields = (
        "batch",
        "deal",
        "provider",
        "provider_name",
        "request_log",
        "premium",
        "vat",
        "total",
        "currency",
        "plan_name",
        "response_time_ms",
        "ranking",
        "coverage_score",
        "status",
        "error_message",
        "normalized_response",
        "raw_response",
        "created_at",
    )
