from aiohttp import web

from pulpcore.plugin.content import app
from pulp_container.app.registry import Registry

registry = Registry()

app.add_routes(
    [
        web.get(
            r"/pulp/container/{path:.+}/{content:(blobs|manifests|config-blobs)}/sha256:{digest:.+}",  # noqa: E501
            registry.get_by_digest,
        )
    ]
)
app.add_routes([web.get(r"/pulp/container/{path:.+}/manifests/{tag_name}", registry.get_tag)])
