from django.urls import include, path
from rest_framework.routers import Route, SimpleRouter
from pulp_container.app.registry_api import (
    BearerTokenView,
    Blobs,
    BlobUploads,
    CatalogView,
    Manifests,
    TagsListView,
    VersionView,
)


router = SimpleRouter(trailing_slash=False)

head_route = Route(
    url=r"^{prefix}/{lookup}{trailing_slash}$",
    mapping={"head": "head"},
    name="{basename}-detail",
    detail=True,
    initkwargs={"suffix": "Instance"},
)

router.routes.append(head_route)
router.register(r"^v2/(?P<path>.+)/blobs/uploads\/?", BlobUploads, basename="docker-upload")
router.register(r"^v2/(?P<path>.+)/blobs", Blobs, basename="blobs")
router.register(r"^v2/(?P<path>.+)/manifests", Manifests, basename="manifests")

urlpatterns = [
    path("token/", BearerTokenView.as_view()),
    path("v2/", VersionView.as_view()),
    path("v2/_catalog", CatalogView.as_view()),
    path("v2/<path:path>/tags/list", TagsListView.as_view()),
    path("", include(router.urls)),
]
