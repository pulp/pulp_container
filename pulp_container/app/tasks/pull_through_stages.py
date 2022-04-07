from urllib.parse import urljoin

from pulpcore.plugin.models import Repository

from pulp_container.app.models import ContainerRemote
from pulp_container.app.tasks.synchronize import ContainerDeclarativeVersion
from pulp_container.app.tasks.sync_stages import ContainerFirstStage, V2_ACCEPT_HEADERS


def pull_tag_from_remote(tag_name, remote_pk, repository_pk, signed_only):
    remote = ContainerRemote.objects.get(pk=remote_pk)
    repository = Repository.objects.get(pk=repository_pk)

    first_stage = PullThroughFirstStage(tag_name, remote, signed_only)
    dv = ContainerDeclarativeVersion(first_stage, repository)
    return dv.create()


class PullThroughFirstStage(ContainerFirstStage):

    def __init__(self, tag_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tag_name = tag_name

    async def run(self):
        relative_url = "/v2/{name}/manifests/{tag}".format(
            name=self.remote.namespaced_upstream_name, tag=self.tag_name
        )
        url = urljoin(self.remote.url, relative_url)
        downloader = self.remote.get_downloader(url=url)
        download_tag = downloader.run(extra_data={"headers": V2_ACCEPT_HEADERS})

        signature_source = None
        pb_parsed_tags = ProgressReportMockUp()

        await self.process_single_tag(download_tag, signature_source, pb_parsed_tags)

        # resolve remaining declarative content
        await self.resolve_flush()


class ProgressReportMockUp:
    async def aincrement(self):
        pass
