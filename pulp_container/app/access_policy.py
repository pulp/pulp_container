from rest_access_policy import AccessPolicy

from pulpcore.plugin.models import AccessPolicy as AccessPolicyModel
from pulpcore.plugin.access_policy import AccessPolicyFromDB

from pulp_container.app import models


class NamespacePermissionsChecker:
    """
    A class that contains a function which checks permissions required for modifying namespaces.
    """

    @staticmethod
    def has_permissions(namespace, user, permission):
        """
        Check whether a user have permissions to manage the passed namespace.
        """

        try:
            namespace = models.ContainerNamespace.objects.get(name=namespace)
        except models.ContainerNamespace.DoesNotExist:
            # check model permissions for namespace creation
            return user.has_perm("container.add_containernamespace")
        else:
            # existing namespace
            return user.has_perm(permission) or user.has_perm(permission, namespace)


class DistributionAccessPolicyMixin:
    """
    Access policy mixin for DistributionViewSet which handles namespace permissions.
    """

    def has_manage_namespace_dist_perms(self, request, view, action, permission):
        """
        Check whether a user can create a namespace or it can manage distributions
        for existing namespace.
        """
        namespace = request.data["base_path"].split("/")[0]
        return NamespacePermissionsChecker.has_permissions(namespace, request.user, permission)

    def has_namespace_obj_perms(self, request, view, action, permission):
        """
        Check if a user has object-level perms on the namespace associated with the distribution.
        """
        namespace = view.get_object().namespace
        return request.user.has_perm(permission, namespace)

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


class DistributionAccessPolicyFromDB(AccessPolicyFromDB, DistributionAccessPolicyMixin):
    """
    Access policy for DistributionViewSet which handles namespace permissions.
    """


class RegistryAccessPolicy(AccessPolicy, DistributionAccessPolicyMixin):
    """
    An AccessPolicy that loads statements from the container distribution viewset.
    """

    def get_policy_statements(self, request, view):
        """
        Return the policy statements for the container distribution viewset.

        Args:
            request (rest_framework.request.Request): The request being checked for authorization.
            view (subclass rest_framework.viewsets.GenericViewSet): The view name being requested.

        Returns:
            The access policy statements in drf-access-policy policy structure.

        """

        access_policy_obj = AccessPolicyModel.objects.get(
            viewset_name="distributions/container/container"
        )
        return access_policy_obj.statements
