from rest_access_policy import AccessPolicy

from pulpcore.plugin.models import AccessPolicy as AccessPolicyModel
from pulpcore.plugin.access_policy import AccessPolicyFromDB

from pulp_container.app import models


class NamespacedAccessPolicyMixin:
    """
    Access policy mixin for ContainerDistributionViewSet and ContainerPushRepositoryViewSet which
    handles namespace permissions.
    """

    def has_namespace_obj_perms(self, request, view, action, permission):
        """
        Check if a user has object-level perms on the namespace associated with the distribution
        or repository.
        """
        if request.user.has_perm(permission):
            return True
        obj = view.get_object()
        if type(obj) == models.ContainerDistribution:
            namespace = obj.namespace
            return request.user.has_perm(permission, namespace)
        elif type(obj) == models.ContainerPushRepository:
            dists_qs = models.ContainerDistribution.objects.filter(repository=obj)
            for dist in dists_qs:
                if request.user.has_perm(permission, dist.namespace):
                    return True
        return False

    def has_namespace_or_obj_perms(self, request, view, action, permission):
        """
        Check if a user has a namespace-level perms or object-level permission
        """
        ns_perm = "container.namespace_{}".format(permission.split(".", 1)[1])
        if self.has_namespace_obj_perms(request, view, action, ns_perm):
            return True
        else:
            return request.user.has_perm(permission) or request.user.has_perm(
                permission, view.get_object()
            )

    def obj_exists(self, request, view, action):
        """
        Check if the distribution exists.
        """
        return view.get_object() is not None

    def is_private(self, request, view, action):
        """
        Check if the distribution is marked private.
        """
        return view.get_object().private


class NamespacedAccessPolicyFromDB(AccessPolicyFromDB, NamespacedAccessPolicyMixin):
    """
    Access policy for ContainerDistributionViewSet and ContainerPushRepositoryViewSet which handles
    namespace permissions.
    """


class NamespaceAccessPolicy(AccessPolicyFromDB):
    """
    Access policy for ContainerNamespaceViewSet.
    """

    def namespace_is_username(self, request, view, action):
        """
        Check if the namespace in the request matches the username.
        """
        return request.data.get("name") == request.user.username


class RegistryAccessPolicy(AccessPolicy, NamespacedAccessPolicyMixin):
    """
    An AccessPolicy that loads statements from the ContainerDistribution, ContainerNamespace,
    and ContainerPushRepository viewsets.
    """

    def get_policy_statements(self, request, view):
        """
        Return the policy statements for the container distribution and namespace viewsets.

        Args:
            request (rest_framework.request.Request): The request being checked for authorization.
            view (subclass rest_framework.viewsets.GenericViewSet): The view name being requested.

        Returns:
            The access policy statements in drf-access-policy policy structure.

        """
        if isinstance(view.get_object(), models.ContainerDistribution):
            access_policy_obj = AccessPolicyModel.objects.get(
                viewset_name="distributions/container/container"
            )
        else:
            access_policy_obj = AccessPolicyModel.objects.get(
                viewset_name="pulp_container/namespaces"
            )
        return access_policy_obj.statements

    def namespace_is_username(self, request, view, action):
        """
        Check if the namespace in the request matches the username.
        """
        return request.data.get("name") == request.user.username
