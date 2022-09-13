from django.db import migrations

from pulp_container.constants import MEDIA_TYPE


def update_schema_media_type(apps, schema_editor):
    Manifest = apps.get_model("container", "Manifest")
    Manifest.objects.filter(media_type=MEDIA_TYPE.MANIFEST_V1_SIGNED).update(
        media_type=MEDIA_TYPE.MANIFEST_V1
    )


class Migration(migrations.Migration):

    dependencies = [("container", "0033_raise_warning_for_repair")]

    operations = [
        migrations.RunPython(
            code=update_schema_media_type,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]
