from aiohttp import web
from django.conf import settings

from pulpcore.plugin.content import app
from pulp_container.app.registry import Registry

registry = Registry()

PREFIX = "/pulp/container/{pulp_domain}/" if settings.DOMAIN_ENABLED else "/pulp/container/"

app.add_routes(
    [
        web.get(
            PREFIX + r"{path:.+}/{content:(blobs|manifests)}/sha256:{digest:.+}",
            registry.get_by_digest,
        )
    ]
)
app.add_routes([web.get(PREFIX + r"{path:.+}/manifests/{tag_name}", registry.get_tag)])
