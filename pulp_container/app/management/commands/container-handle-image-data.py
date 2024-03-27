from json.decoder import JSONDecodeError

from gettext import gettext as _

from contextlib import suppress

from django.core.exceptions import ObjectDoesNotExist
from django.core.management import BaseCommand

from pulp_container.app.models import Manifest

from pulp_container.constants import MEDIA_TYPE


class Command(BaseCommand):
    """
    A management command to handle the initialization of empty DB fields for container images.

    This command now initializes flags describing the image nature.

    Manifests stored inside Pulp are of various natures. The nature of an image can be determined
    from JSON-formatted image manifest annotations or image configuration labels. These data are
    stored inside artifacts.

    This command reads data from the storage backend and populates the 'annotations', 'labels',
    'is_bootable', and 'is_flatpak' fields on the Manifest model.
    """

    help = _(__doc__)

    def handle(self, *args, **options):
        manifests_updated_count = 0

        manifests = Manifest.objects.filter(labels={}, annotations={})
        manifests = manifests.exclude(
            media_type__in=[MEDIA_TYPE.MANIFEST_LIST, MEDIA_TYPE.INDEX_OCI, MEDIA_TYPE.MANIFEST_V1]
        )
        manifests_updated_count += self.update_manifests(manifests)

        manifest_lists = Manifest.objects.filter(
            media_type__in=[MEDIA_TYPE.MANIFEST_LIST, MEDIA_TYPE.INDEX_OCI], annotations={}
        )
        manifests_updated_count += self.update_manifests(manifest_lists)

        self.stdout.write(
            self.style.SUCCESS("Successfully updated %d manifests." % manifests_updated_count)
        )

    def update_manifests(self, manifests_qs):
        manifests_updated_count = 0
        manifests_to_update = []
        for manifest in manifests_qs.iterator():
            # suppress non-existing/already migrated artifacts and corrupted JSON files
            with suppress(ObjectDoesNotExist, JSONDecodeError):
                has_metadata = manifest.init_metadata()
                if has_metadata:
                    manifests_to_update.append(manifest)

            if len(manifests_to_update) > 1000:
                fields_to_update = ["annotations", "labels", "is_bootable", "is_flatpak"]
                manifests_qs.model.objects.bulk_update(
                    manifests_to_update,
                    fields_to_update,
                )
                manifests_updated_count += len(manifests_to_update)
                manifests_to_update.clear()
        if manifests_to_update:
            fields_to_update = ["annotations", "labels", "is_bootable", "is_flatpak"]
            manifests_qs.model.objects.bulk_update(
                manifests_to_update,
                fields_to_update,
            )
            manifests_updated_count += len(manifests_to_update)

        return manifests_updated_count
