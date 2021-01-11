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


class DistributionAccessPolicyFromDB(AccessPolicyFromDB):
    """
    Access policy for DistributionViewSet which handles namespace permissions.
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
