from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("insurance", "0010_provider_quote_models"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="insuranceprovider",
            index=models.Index(
                fields=["is_active", "priority"],
                name="insprov_act_prio_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="quoterequestlog",
            index=models.Index(
                fields=["deal", "provider", "-created_at"],
                name="qreq_deal_prov_ctd_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="quoteresult",
            index=models.Index(
                fields=["deal", "provider", "-created_at"],
                name="qres_deal_prov_ctd_idx",
            ),
        ),
    ]
