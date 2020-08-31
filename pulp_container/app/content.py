from aiohttp import web

from pulpcore.plugin.content import app
from pulp_container.app.registry import Registry

registry = Registry()

app.add_routes(
    [web.get(r"/pulp/container/{path:.+}/blobs/sha256:{digest:.+}", registry.get_by_digest)]
)
app.add_routes(
    [web.get(r"/pulp/container/{path:.+}/manifests/sha256:{digest:.+}", registry.get_by_digest)]
)
app.add_routes([web.get(r"/pulp/container/{path:.+}/manifests/{tag_name}", registry.get_tag)])
