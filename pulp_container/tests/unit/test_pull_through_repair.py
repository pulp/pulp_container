from importlib import import_module
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.exceptions import ValidationError

from pulpcore.plugin.models import Distribution

from pulp_container.app.models import ContainerDistribution, ContainerPullThroughDistribution
from pulp_container.app.pull_through import (
    get_pull_through_distribution,
    get_pull_through_distribution_path,
)
from pulp_container.app.viewsets import ContainerPullThroughDistributionViewSet
from pulp_container.constants import PULL_THROUGH_DISTRIBUTION_LABEL


class TestPullThroughDistributionRepair(TestCase):
    def test_command_repairs_all_legacy_distributions_and_reports_overlaps(self):
        repairable = ContainerPullThroughDistribution.objects.create(
            name="repairable", base_path="repairable"
        )
        different_name = ContainerPullThroughDistribution.objects.create(
            name="unresolved", base_path="different"
        )
        other = Distribution.objects.create(name="other", base_path="other")
        container = ContainerDistribution.objects.create(name="container", base_path="container")
        output = StringIO()

        command_module = import_module(
            "pulp_container.app.management.commands.container-repair-pull-through-distributions"
        )
        with patch.object(
            command_module,
            "find_container_distribution_overlaps",
            return_value=[(container, other)],
        ):
            call_command("container-repair-pull-through-distributions", stdout=output)

        repairable.refresh_from_db()
        different_name.refresh_from_db()
        self.assertNotEqual(repairable.base_path, repairable.name)
        self.assertEqual(
            repairable.pulp_labels,
            {PULL_THROUGH_DISTRIBUTION_LABEL: "repairable"},
        )
        self.assertNotEqual(different_name.base_path, "different")
        self.assertEqual(
            different_name.pulp_labels,
            {PULL_THROUGH_DISTRIBUTION_LABEL: "different"},
        )
        self.assertIn("Repaired 2 pull-through distributions.", output.getvalue())
        self.assertIn(f"pk={container.pk}", output.getvalue())
        self.assertIn(f"pk={other.pk}", output.getvalue())

    @override_settings(CACHE_ENABLED=True)
    def test_command_flushes_repaired_cache_keys(self):
        distribution = ContainerPullThroughDistribution.objects.create(
            name="legacy", base_path="registry-cache"
        )
        command_module = import_module(
            "pulp_container.app.management.commands.container-repair-pull-through-distributions"
        )

        with patch.object(command_module, "SyncContentCache") as cache:
            call_command("container-repair-pull-through-distributions", stdout=StringIO())

        cache.return_value.delete.assert_called_once_with(base_key=["registry-cache"])


class TestPullThroughDistributionLookup(TestCase):
    def test_marked_distribution_matches_on_stored_registry_path(self):
        distribution = ContainerPullThroughDistribution.objects.create(
            name="pull-through distribution",
            base_path=str(uuid4()),
            pulp_labels={PULL_THROUGH_DISTRIBUTION_LABEL: "registry-cache"},
        )

        match = get_pull_through_distribution("registry-cache/library/busybox")

        self.assertEqual(match, distribution)
        self.assertEqual(get_pull_through_distribution_path(match), "registry-cache")

    def test_unmarked_distribution_falls_back_to_base_path(self):
        distribution = ContainerPullThroughDistribution.objects.create(
            name="legacy", base_path="legacy"
        )

        match = get_pull_through_distribution("legacy/library/busybox")

        self.assertEqual(match, distribution)
        self.assertEqual(get_pull_through_distribution_path(match), "legacy")

    def test_match_observes_path_segment_boundaries(self):
        distribution = ContainerPullThroughDistribution.objects.create(
            name="pull-through distribution",
            base_path=str(uuid4()),
            pulp_labels={PULL_THROUGH_DISTRIBUTION_LABEL: "registry-cache"},
        )

        match = get_pull_through_distribution("registry-cache-other/library/busybox")

        self.assertIsNone(match)


class TestPullThroughDistributionLabels(TestCase):
    def test_marker_label_actions_are_registered_and_protected(self):
        actions = {
            action.__name__: action
            for action in ContainerPullThroughDistributionViewSet.get_extra_actions()
        }
        self.assertIn("set_label", actions)
        self.assertIn("unset_label", actions)

        view = ContainerPullThroughDistributionViewSet()
        request = SimpleNamespace(data={"key": PULL_THROUGH_DISTRIBUTION_LABEL})
        with self.assertRaises(ValidationError):
            view.set_label(request)
        with self.assertRaises(ValidationError):
            view.unset_label(request)
