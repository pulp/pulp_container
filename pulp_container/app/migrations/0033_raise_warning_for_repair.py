import warnings

from django.db import migrations

from pulp_container.constants import MEDIA_TYPE


def print_warning_for_repair(apps, schema_editor):
    Manifest = apps.get_model("container", "Manifest")
    if Manifest.objects.filter(media_type=MEDIA_TYPE.MANIFEST_V1).exists():
        warnings.warn(
            "Manifests with potentially invalid media types were detected. Please, run the "
            "'pulpcore-manager container-repair-media-type' command to repair the media types "
            "of the manifests that could be incorrectly parsed during the sync procedure."
        )


class Migration(migrations.Migration):

    dependencies = [('container', '0032_upload_artifact')]

    operations = [
        migrations.RunPython(
            code=print_warning_for_repair,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]
