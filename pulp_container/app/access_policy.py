from pulpcore.plugin.access_policy import AccessPolicyFromDB

from pulp_container.app import models


class DistributionAccessPolicyFromDB(AccessPolicyFromDB):
    """
    Access policy for DistributionViewSet which handles namespace permissions.
    """

    def has_add_namespace_perms(self, request, view, action):
        """
        Check whether a user can create a namespace or can read the namespace if it already exists.
        """
        namespace = request.data["base_path"].split("/")[0]
        try:
            namespace = models.ContainerNamespace.objects.get(name=namespace)
        except models.ContainerNamespace.DoesNotExist:
            return request.user.has_perm("container.add_containernamespace")
        else:
            return request.user.has_perm(
                "container.view_containernamespace"
            ) or request.user.has_perm("container.view_containernamespace", namespace)

    def has_view_namespace_perms(self, request, view, action):
        """
        Test if a user is able read the namespace contained within a distribution.
        """
        namespace = view.get_object().namespace
        return request.user.has_perm("container.view_containernamespace", namespace)
