from django.conf.urls import url

from .viewsets import (
    ManifestCopyViewSet,
    RecursiveAdd,
    RecursiveRemove,
    TagCopyViewSet,
    TagImageViewSet,
    UnTagImageViewSet,
)


urlpatterns = [
    url(r'^pulp/api/v3/container/manifests/copy/$', ManifestCopyViewSet.as_view({'post': 'create'})), # noqa
    url(r'^pulp/api/v3/container/recursive-add/$', RecursiveAdd.as_view({'post': 'create'})),
    url(r'^pulp/api/v3/container/recursive-remove/$', RecursiveRemove.as_view({'post': 'create'})),
    url(r'^pulp/api/v3/container/tag/$', TagImageViewSet.as_view({'post': 'create'})),
    url(r'^pulp/api/v3/container/tags/copy/$', TagCopyViewSet.as_view({'post': 'create'})),
    url(r'^pulp/api/v3/container/untag/$', UnTagImageViewSet.as_view({'post': 'create'}))
]
