from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("insurance", "0018_policy_issuance_status_pending"),
    ]

    operations = [
        migrations.AddField(
            model_name="policyissuance",
            name="dic_request_id",
            field=models.CharField(blank=True, max_length=64),
        ),
    ]
