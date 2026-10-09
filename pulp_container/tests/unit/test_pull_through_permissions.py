from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, User
from django.test import SimpleTestCase, override_settings

from pulpcore.plugin.models import Domain

from pulp_container.app.authorization import PermissionChecker
from pulp_container.app.models import (
    ContainerDistribution,
    ContainerNamespace,
    ContainerPullThroughDistribution,
)
from pulp_container.app.viewsets import (
    ContainerDistributionViewSet,
    ContainerNamespaceViewSet,
    ContainerPullThroughDistributionViewSet,
)


@override_settings(DOMAIN_ENABLED=False)
class TestPullThroughPermissions(SimpleTestCase):
    def setUp(self):
        self.domain = Domain(name="default")
        self.namespace = ContainerNamespace(name="cache", pulp_domain=self.domain)
        self.policies = {
            "pulp_container/namespaces": ContainerNamespaceViewSet.DEFAULT_ACCESS_POLICY,
            "distributions/container/container": ContainerDistributionViewSet.DEFAULT_ACCESS_POLICY,
            "distributions/container/pull-through": (
                ContainerPullThroughDistributionViewSet.DEFAULT_ACCESS_POLICY
            ),
        }
        self.enterContext(
            patch("pulp_container.app.authorization.get_domain", return_value=self.domain)
        )
        self.enterContext(
            patch(
                "pulp_container.app.access_policy.AccessPolicyModel.objects.get",
                side_effect=lambda viewset_name: SimpleNamespace(
                    statements=self.policies[viewset_name]["statements"]
                ),
            )
        )

    def test_new_distribution_pull_permissions(self):
        for private in (False, True):
            for user in (AnonymousUser(), User(username="reader")):
                with self.subTest(private=private, user=user):
                    distribution = ContainerPullThroughDistribution(
                        private=private, namespace=self.namespace, pulp_domain=self.domain
                    )
                    with (
                        patch.object(user, "has_perm", return_value=False),
                        patch(
                            "pulp_container.app.authorization.ContainerDistribution.objects.get",
                            side_effect=ContainerDistribution.DoesNotExist,
                        ),
                        patch(
                            "pulp_container.app.authorization.ContainerNamespace.objects.get",
                            return_value=self.namespace,
                        ),
                        patch(
                            "pulp_container.app.authorization.get_pull_through_distribution",
                            return_value=distribution,
                        ),
                    ):
                        self.assertEqual(
                            PermissionChecker(user).has_pull_permissions("cache/library/image"),
                            not private,
                        )

    def test_new_content_pull_permissions(self):
        for private in (False, True):
            for user in (AnonymousUser(), User(username="reader")):
                with self.subTest(private=private, user=user):
                    distribution = ContainerDistribution(
                        private=private, namespace=self.namespace, pulp_domain=self.domain
                    )
                    with patch.object(user, "has_perm", return_value=False):
                        self.assertEqual(
                            PermissionChecker(user).has_pull_through_new_content_permissions(
                                distribution
                            ),
                            not private,
                        )

    def test_authorized_user_can_pull_through_private_distribution(self):
        user = User(username="consumer")
        distribution = ContainerPullThroughDistribution(
            private=True, namespace=self.namespace, pulp_domain=self.domain
        )
        cached_distribution = ContainerDistribution(
            private=True, namespace=self.namespace, pulp_domain=self.domain
        )
        with patch.object(user, "has_perm", return_value=True):
            checker = PermissionChecker(user)
            self.assertTrue(checker.has_pull_through_new_distribution_permissions(distribution))
            self.assertTrue(checker.has_pull_through_new_content_permissions(cached_distribution))

    def test_custom_policy_can_deny_public_pull_through(self):
        self.policies = {name: {"statements": []} for name in self.policies}
        checker = PermissionChecker(AnonymousUser())
        self.assertFalse(
            checker.has_pull_through_new_distribution_permissions(
                ContainerPullThroughDistribution(
                    private=False, namespace=self.namespace, pulp_domain=self.domain
                )
            )
        )
        self.assertFalse(
            checker.has_pull_through_new_content_permissions(
                ContainerDistribution(
                    private=False, namespace=self.namespace, pulp_domain=self.domain
                )
            )
        )
