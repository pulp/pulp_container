import json
import logging

from pulpcore.plugin.stages import DeclarativeContent

from pulp_container.app.models import ContainerRemote, ContainerRepository, Tag
from pulp_container.app.utils import determine_media_type_from_json
from pulp_container.constants import MEDIA_TYPE

from .synchronize import ContainerDeclarativeVersion
from .sync_stages import ContainerFirstStage

log = logging.getLogger(__name__)


def download_image_data(repository_pk, remote_pk, raw_text_manifest_data, tag_name):
    repository = ContainerRepository.objects.get(pk=repository_pk)
    remote = ContainerRemote.objects.get(pk=remote_pk)
    log.info("Pulling cache: repository={r} remote={p}".format(r=repository.name, p=remote.name))
    first_stage = ContainerPullThroughFirstStage(remote, raw_text_manifest_data, tag_name)
    dv = ContainerDeclarativeVersion(first_stage, repository)
    return dv.create()


class ContainerPullThroughFirstStage(ContainerFirstStage):
    """The stage that prepares the pipeline for downloading a single tag and its related data."""

    def __init__(self, remote, raw_text_manifest_data, tag_name):
        """Initialize the stage with the artifact defined in content-app."""
        super().__init__(remote, signed_only=False)
        self.tag_name = tag_name
        self.raw_text_manifest_data = raw_text_manifest_data

    async def run(self):
        """Run the stage and create declarative content for one tag, its manifest, and blobs.

        This method is a tinified method based on ``ContainerFirstStage.run`` with syncing just
        a single tag.
        """
        tag_dc = DeclarativeContent(Tag(name=self.tag_name))
        self.tag_dcs.append(tag_dc)

        content_data = json.loads(self.raw_text_manifest_data)

        media_type = determine_media_type_from_json(content_data)
        if media_type in (MEDIA_TYPE.MANIFEST_LIST, MEDIA_TYPE.INDEX_OCI):
            list_dc = self.create_manifest_list(
                content_data, self.raw_text_manifest_data, media_type
            )
            for manifest_data in content_data.get("manifests"):
                listed_manifest = await self.create_listed_manifest(manifest_data)
                list_dc.extra_data["listed_manifests"].append(listed_manifest)
            else:
                tag_dc.extra_data["tagged_manifest_dc"] = list_dc
                for listed_manifest in list_dc.extra_data["listed_manifests"]:
                    await self.handle_blobs(
                        listed_manifest["manifest_dc"], listed_manifest["content_data"]
                    )
                    self.manifest_dcs.append(listed_manifest["manifest_dc"])
                self.manifest_list_dcs.append(list_dc)
        else:
            # Simple tagged manifest
            man_dc = self.create_manifest(content_data, self.raw_text_manifest_data, media_type)
            tag_dc.extra_data["tagged_manifest_dc"] = man_dc
            await self.handle_blobs(man_dc, content_data)
            self.manifest_dcs.append(man_dc)

        await self.resolve_flush()
