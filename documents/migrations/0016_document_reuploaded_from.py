from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0015_document_ocr_data"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="reuploaded_from",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="reuploads",
                to="documents.document",
            ),
        ),
    ]
