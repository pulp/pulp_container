import json

from gettext import gettext as _

from django.core.management import BaseCommand

from pulp_container.app.models import Manifest
from pulp_container.app.utils import determine_media_type_from_json

from pulp_container.constants import MEDIA_TYPE


class Command(BaseCommand):
    """
    A django management command to repair the media types of manifests.

    Older versions of pulp_container could sometimes assign an invalid media type to a manifest.
    If the media type could not be extracted from the Content-Type header, the sync pipeline
    assumed that the media type is "application/vnd.docker.distribution.manifest.v1+json". The
    repair command iterates over synced manifests and updates their media types based on the
    internals of the associated manifest.json files if needed.

    This command also deletes the cache for all distributions across the plugin.
    """

    help = _(__doc__)

    def handle(self, *args, **options):
        """Run the management command."""
        manifests_schema_v1 = Manifest.objects.filter(
            media_type=MEDIA_TYPE.MANIFEST_V1
        ).prefetch_related("_artifacts")

        manifests_to_update = []
        for manifest in manifests_schema_v1:
            artifact_file = manifest._artifacts.first().file
            json_data = json.load(artifact_file)
            artifact_file.close()

            media_type = determine_media_type_from_json(json_data)
            if media_type != MEDIA_TYPE.MANIFEST_V1:
                manifest.media_type = media_type
                manifests_to_update.append(manifest)

        if manifests_to_update:
            Manifest.objects.bulk_update(manifests_to_update, ["media_type"], batch_size=100)

        manifests_schema_v1_signed = Manifest.objects.filter(
            media_type=MEDIA_TYPE.MANIFEST_V1_SIGNED
        )
        manifests_schema_v1_signed.update(media_type=MEDIA_TYPE.MANIFEST_V1)
        self.stdout.write(
            self.style.SUCCESS(
                "Successfully repaired %d manifests."
                % (len(manifests_to_update) + len(manifests_schema_v1_signed))
            )
        )
