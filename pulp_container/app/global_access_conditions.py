from logging import getLogger

from pulpcore.plugin.models import Repository
from pulpcore.plugin.viewsets import RepositoryVersionViewSet

from pulp_container.app import models
from pulp_container.app.viewsets import ContainerDistributionViewSet

_logger = getLogger(__name__)


def has_namespace_obj_perms(request, view, action, permission):
    """
    Check if a user has object-level perms on the namespace associated with the distribution
    or repository.
    """
    if request.user.has_perm(permission):
        return True
    if isinstance(view, RepositoryVersionViewSet):
        obj = Repository.objects.get(pk=view.kwargs["repository_pk"]).cast()
    else:
        obj = view.get_object()
    if type(obj) is models.ContainerDistribution:
        namespace = obj.namespace
        return request.user.has_perm(permission, namespace)
    elif type(obj) is models.ContainerPushRepository:
        for dist in obj.distributions.all():
            if request.user.has_perm(permission, dist.cast().namespace):
                return True
    elif type(obj) is models.ContainerPullThroughDistribution:
        namespace = obj.namespace
        return request.user.has_perm(permission, namespace)
    return False


def has_namespace_perms(request, view, action, permission):
    """
    Check if a user has a namespace-level permission
    """
    view.get_serializer(data=request.data).is_valid(raise_exception=True)
    ns_perm = "container.namespace_{}".format(permission.split(".", 1)[1])
    base_path = request.data.get("base_path")
    if not base_path:
        return False
    namespace = base_path.split("/")[0]
    try:
        namespace = models.ContainerNamespace.objects.get(name=namespace)
    except models.ContainerNamespace.DoesNotExist:
        return False
    else:
        return request.user.has_perm(permission) or request.user.has_perm(ns_perm, namespace)


def has_namespace_or_obj_perms(request, view, action, permission):
    """
    Check if a user has a namespace-level perms or object-level permission
    """
    ns_perm = "container.namespace_{}".format(permission.split(".", 1)[1])
    if has_namespace_obj_perms(request, view, action, ns_perm):
        return True
    else:
        return request.user.has_perm(permission) or request.user.has_perm(
            permission, view.get_object()
        )


def obj_exists(request, view, action):
    """
    Check if the distribution exists.
    """
    return view.get_object() is not None


def is_private(request, view, action):
    """
    Check if the distribution is marked private.
    """
    return view.get_object().private


def namespace_is_username(request, view, action):
    """
    Check if the namespace in the request matches the username.
    """
    view.get_serializer(data=request.data).is_valid(raise_exception=True)
    if isinstance(view, ContainerDistributionViewSet):
        base_path = request.data.get("base_path")
        if not base_path:
            return False
        namespace = base_path.split("/")[0]
    else:
        namespace = request.data.get("name")
    return namespace == request.user.username


def has_namespace_model_perms(request, view, action):
    """
    Check if the user can create namespaces.
    """
    if request.user.has_perm("container.add_containernamespace"):
        return True
    return False


def has_distribution_perms(request, view, action, permission):
    """
    Check if the user has permissions on the corresponding distribution.
    Model or object permission is sufficient.
    """
    if request.user.has_perm(permission):
        return True
    if "repository_pk" in view.kwargs:
        repository = Repository.objects.get(pk=view.kwargs["repository_pk"])
    else:
        repository = view.get_object()
    distributions = repository.distributions.all()
    return any(
        (request.user.has_perm(permission, distribution.cast()) for distribution in distributions)
    )
