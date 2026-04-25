# Generated manually because the local shell does not have Django installed.

from django.db import migrations, models

import documents.models


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0013_alter_document_options_document_document_type_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="document",
            name="file",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to=documents.models.unique_document_upload_path,
            ),
        ),
    ]
