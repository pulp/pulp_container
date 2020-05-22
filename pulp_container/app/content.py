from aiohttp import web

from pulpcore.plugin.content import app
from pulp_container.app.authorization import AuthorizationService
from pulp_container.app.registry import Registry

registry = Registry()

app.add_routes([web.get('/v2/', registry.serve_v2)])
app.add_routes([web.get('/v2/_catalog', registry.list_repositories)])
app.add_routes([web.get(r'/v2/{path:.+}/blobs/sha256:{digest:.+}', registry.get_by_digest)])
app.add_routes([web.get(r'/v2/{path:.+}/manifests/sha256:{digest:.+}', registry.get_by_digest)])
app.add_routes([web.get(r'/v2/{path:.+}/manifests/{tag_name}', registry.get_tag)])
app.add_routes([web.get(r'/v2/{path:.+}/tags/list', registry.tags_list)])

authorization_service = AuthorizationService()

app.add_routes([web.get('/token', authorization_service.generate_token)])
