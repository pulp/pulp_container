from json.decoder import JSONDecodeError

from gettext import gettext as _

from contextlib import suppress

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.management import BaseCommand
from django.db.models import Q

from pulpcore.plugin.cache import SyncContentCache

from pulp_container.app.models import ContainerDistribution, Manifest

from pulp_container.app.utils import get_content_data

from pulp_container.constants import MEDIA_TYPE


class Command(BaseCommand):
    """
    A management command to handle the initialization of empty DB fields for container images.

    This command initializes flags describing the image nature and moves the manifest's artifact
    data into the database.

    Manifests stored inside Pulp are of various natures. The nature of an image can be determined
    from JSON-formatted image manifest annotations or image configuration labels. These data are
    stored inside artifacts.

    This command reads data from the storage backend and populates the 'annotations', 'labels',
    'is_bootable', 'is_flatpak', and 'data' fields on the Manifest model. Note that the Redis
    cache will be flushed if there is any.
    """

    help = _(__doc__)

    def handle(self, *args, **options):
        manifests_updated_count = 0

        manifests_v1 = Manifest.objects.filter(
            Q(media_type=MEDIA_TYPE.MANIFEST_V1),
            Q(data__isnull=True)
            | Q(type__isnull=True)
            | Q(architecture__isnull=True)
            | Q(os__isnull=True)
            | Q(compressed_image_size__isnull=True),
        )
        manifests_updated_count += self.update_manifests(manifests_v1)

        manifests_v2 = Manifest.objects.filter(
            Q(data__isnull=True)
            | Q(annotations={}, labels={})
            | Q(type__isnull=True)
            | Q(architecture__isnull=True)
            | Q(os__isnull=True)
            | Q(compressed_image_size__isnull=True)
        )
        manifests_v2 = manifests_v2.exclude(
            media_type__in=[MEDIA_TYPE.MANIFEST_LIST, MEDIA_TYPE.INDEX_OCI, MEDIA_TYPE.MANIFEST_V1]
        )
        manifests_updated_count += self.update_manifests(manifests_v2)

        manifest_lists = Manifest.objects.filter(
            Q(media_type__in=[MEDIA_TYPE.MANIFEST_LIST, MEDIA_TYPE.INDEX_OCI]),
            Q(data__isnull=True) | Q(annotations={}),
        )
        manifests_updated_count += self.update_manifests(manifest_lists)

        self.stdout.write(
            self.style.SUCCESS("Successfully updated %d manifests." % manifests_updated_count)
        )

        if settings.CACHE_ENABLED and manifests_updated_count != 0:
            base_paths = ContainerDistribution.objects.values_list("base_path", flat=True)
            if base_paths:
                SyncContentCache().delete(base_key=base_paths)

            self.stdout.write(self.style.SUCCESS("Successfully flushed the cache."))

    def update_manifests(self, manifests_qs):
        manifests_updated_count = 0
        manifests_to_update = []
        fields_to_update = [
            "annotations",
            "labels",
            "is_bootable",
            "is_flatpak",
            "data",
            "type",
            "os",
            "architecture",
            "compressed_image_size",
        ]

        for manifest in manifests_qs.iterator():
            # suppress non-existing/already migrated artifacts and corrupted JSON files
            with suppress(ObjectDoesNotExist, JSONDecodeError):
                needs_update = self.init_manifest(manifest)
                if needs_update:
                    manifests_to_update.append(manifest)

            if len(manifests_to_update) > 1000:
                manifests_qs.model.objects.bulk_update(
                    manifests_to_update,
                    fields_to_update,
                )
                manifests_updated_count += len(manifests_to_update)
                manifests_to_update.clear()

        if manifests_to_update:
            manifests_qs.model.objects.bulk_update(
                manifests_to_update,
                fields_to_update,
            )
            manifests_updated_count += len(manifests_to_update)

        return manifests_updated_count

    def init_manifest(self, manifest):
        updated = False
        if not manifest.data:
            manifest_artifact = manifest._artifacts.get()
            manifest_data, raw_bytes_data = get_content_data(manifest_artifact)
            manifest.data = raw_bytes_data.decode("utf-8")

            if not (manifest.annotations or manifest.labels or manifest.type):
                manifest.init_metadata(manifest_data)

            if self.needs_os_arch_size_update(manifest):
                self.init_manifest_os_arch_size(manifest)
            manifest._artifacts.clear()
            updated = True

        if not manifest.type:
            updated = manifest.init_image_nature()

        if self.needs_os_arch_size_update(manifest):
            self.init_manifest_os_arch_size(manifest)
            updated = True

        return updated

    def needs_os_arch_size_update(self, manifest):
        return manifest.media_type not in [MEDIA_TYPE.MANIFEST_LIST, MEDIA_TYPE.INDEX_OCI] and not (
            manifest.architecture or manifest.os or manifest.compressed_image_size
        )

    def init_manifest_os_arch_size(self, manifest):
        manifest.init_architecture_and_os()
        manifest.init_compressed_image_size()
