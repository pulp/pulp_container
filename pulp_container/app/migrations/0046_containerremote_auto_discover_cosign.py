from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("container", "0045_alter_manifest_compressed_image_size"),
    ]

    operations = [
        migrations.AddField(
            model_name="containerremote",
            name="auto_discover_cosign",
            field=models.BooleanField(default=True),
        ),
    ]
