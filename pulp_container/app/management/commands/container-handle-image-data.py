import json

from json.decoder import JSONDecodeError

from gettext import gettext as _

from contextlib import suppress

from django.core.exceptions import ObjectDoesNotExist
from django.core.management import BaseCommand
from django.db.models import Q

from pulp_container.app.models import Manifest

from pulp_container.app.utils import get_content_data

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

        manifests = Manifest.objects.filter(Q(data="") | Q(annotations={}, labels={}))
        manifests = manifests.exclude(
            media_type__in=[MEDIA_TYPE.MANIFEST_LIST, MEDIA_TYPE.INDEX_OCI, MEDIA_TYPE.MANIFEST_V1]
        )
        manifests_updated_count += self.update_manifests(manifests)

        manifest_lists = Manifest.objects.filter(
            Q(media_type__in=[MEDIA_TYPE.MANIFEST_LIST, MEDIA_TYPE.INDEX_OCI]),
            Q(data="") | Q(annotations={}),
        )
        manifests_updated_count += self.update_manifests(manifest_lists)

        self.stdout.write(
            self.style.SUCCESS("Successfully updated %d manifests." % manifests_updated_count)
        )

    def init_manifest(self, manifest):
        has_initialized_data = manifest.data != ""
        if has_initialized_data:
            manifest_data = json.loads(manifest.data)
        else:
            manifest_artifact = manifest._artifacts.get()
            manifest_data, raw_bytes_data = get_content_data(manifest_artifact)
            manifest.data = raw_bytes_data.decode("utf-8")
            manifest._artifacts.clear()

        manifest.annotations = manifest_data.get("annotations", {})

        has_annotations = bool(manifest.annotations)
        has_labels = manifest.init_labels()
        has_image_nature = manifest.init_image_nature()

        return has_annotations or has_labels or has_image_nature or (not has_initialized_data)

    def update_manifests(self, manifests_qs):
        manifests_updated_count = 0
        manifests_to_update = []
        for manifest in manifests_qs.iterator():
            # suppress non-existing/already migrated artifacts and corrupted JSON files
            with suppress(ObjectDoesNotExist, JSONDecodeError):
                needs_update = self.init_manifest(manifest)
                if needs_update:
                    manifests_to_update.append(manifest)

            if len(manifests_to_update) > 1000:
                fields_to_update = ["annotations", "labels", "is_bootable", "is_flatpak", "data"]
                manifests_qs.model.objects.bulk_update(
                    manifests_to_update,
                    fields_to_update,
                )
                manifests_updated_count += len(manifests_to_update)
                manifests_to_update.clear()
        if manifests_to_update:
            fields_to_update = ["annotations", "labels", "is_bootable", "is_flatpak", "data"]
            manifests_qs.model.objects.bulk_update(
                manifests_to_update,
                fields_to_update,
            )
            manifests_updated_count += len(manifests_to_update)

        return manifests_updated_count
