from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0014_alter_document_file_unique_upload_path"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="ocr_data",
            field=models.JSONField(blank=True, null=True),
        ),
    ]
