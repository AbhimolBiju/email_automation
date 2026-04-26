from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("deals", "0005_merge_20260424_ocr_motor_branches"),
        ("insurance", "0009_alter_insuranceinfo_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="InsuranceProvider",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                ("code", models.CharField(max_length=50, unique=True)),
                ("base_url", models.URLField(blank=True)),
                ("api_key", models.CharField(blank=True, max_length=255)),
                ("username", models.CharField(blank=True, max_length=255)),
                ("password", models.CharField(blank=True, max_length=255)),
                ("extra_config", models.JSONField(blank=True, default=dict)),
                ("timeout", models.PositiveIntegerField(default=30)),
                ("priority", models.PositiveIntegerField(default=100)),
                ("is_active", models.BooleanField(default=True)),
                ("provider_class", models.CharField(max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["priority", "name"]},
        ),
        migrations.CreateModel(
            name="QuoteRequestLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("request_payload", models.JSONField(blank=True, default=dict)),
                ("response_payload", models.JSONField(blank=True, default=dict)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("success", "Success"), ("failed", "Failed"), ("skipped", "Skipped")], default="pending", max_length=20)),
                ("latency_ms", models.PositiveIntegerField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("deal", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="quote_request_logs", to="deals.deal")),
                ("provider", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="quote_request_logs", to="insurance.insuranceprovider")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="QuoteResult",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("premium", models.DecimalField(decimal_places=2, max_digits=12)),
                ("vat", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("total", models.DecimalField(decimal_places=2, max_digits=12)),
                ("currency", models.CharField(default="AED", max_length=10)),
                ("plan_name", models.CharField(max_length=255)),
                ("response_time_ms", models.PositiveIntegerField(default=0)),
                ("raw_response", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("deal", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="quote_results", to="deals.deal")),
                ("provider", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="quote_results", to="insurance.insuranceprovider")),
                ("request_log", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="quote_results", to="insurance.quoterequestlog")),
            ],
            options={"ordering": ["total", "provider__priority", "-created_at"]},
        ),
    ]
