from logging import getLogger

from rest_access_policy import AccessPolicy

from pulpcore.plugin.models import AccessPolicy as AccessPolicyModel

from pulp_container.app import models

_logger = getLogger(__name__)


class RegistryAccessPolicy(AccessPolicy):
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
        elif isinstance(view.get_object(), models.ContainerPullThroughDistribution):
            access_policy_obj = AccessPolicyModel.objects.get(
                viewset_name="distributions/container/pull-through"
            )
        else:
            access_policy_obj = AccessPolicyModel.objects.get(
                viewset_name="pulp_container/namespaces"
            )
        return access_policy_obj.statements
