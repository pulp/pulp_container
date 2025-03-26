from django.conf import settings
from django.urls import include, path
from rest_framework.routers import Route, SimpleRouter
from pulp_container.app.registry_api import (
    BearerTokenView,
    Blobs,
    BlobUploads,
    CatalogView,
    FlatpakIndexDynamicView,
    FlatpakIndexStaticView,
    Manifests,
    Signatures,
    TagsListView,
    VersionView,
)

if settings.DOMAIN_ENABLED:
    re_path = "(?P<pulp_domain>[-a-zA-Z0-9_]+)/(?P<path>.+)"
    da_path = "<slug:pulp_domain>/<path:path>"
else:
    re_path = "(?P<path>.+)"
    da_path = "<path:path>"

router = SimpleRouter(trailing_slash=False)

head_route = Route(
    url=r"^{prefix}/{lookup}{trailing_slash}$",
    mapping={"head": "head"},
    name="{basename}-detail",
    detail=True,
    initkwargs={"suffix": "Instance"},
)

router.routes.append(head_route)
router.register(rf"v2/{re_path}/blobs/uploads\/?", BlobUploads, basename="docker-upload")
router.register(rf"v2/{re_path}/blobs", Blobs, basename="blobs")
router.register(rf"v2/{re_path}/manifests", Manifests, basename="manifests")
router.register(rf"extensions/v2/{re_path}/signatures", Signatures, basename="signatures")

urlpatterns = [
    path("token/", BearerTokenView.as_view()),
    path("v2/", VersionView.as_view()),
    path("v2/_catalog", CatalogView.as_view()),
    path(f"v2/{da_path}/tags/list", TagsListView.as_view()),
    path("", include(router.urls)),
]
# print(router.urls)
if settings.FLATPAK_INDEX:
    urlpatterns.extend(
        [
            path("index/dynamic", FlatpakIndexDynamicView.as_view()),
            path("index/static", FlatpakIndexStaticView.as_view()),
        ]
    )
