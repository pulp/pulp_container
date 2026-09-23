from django.db.models import F, Q, TextField, Value
from django.db.models.functions import Concat

from pulpcore.plugin.models import Distribution

from pulp_container.app.models import ContainerDistribution, ContainerPullThroughDistribution
from pulp_container.constants import (
    PULL_THROUGH_DISTRIBUTION_LABEL,
)


def is_pull_through_distribution_marked(distribution):
    """Return whether a pull-through distribution stores its registry path in pulp_labels."""
    return (distribution.pulp_labels or {}).get(PULL_THROUGH_DISTRIBUTION_LABEL)


def get_pull_through_distribution_path(distribution):
    """Return the registry path represented by a pull-through distribution."""
    if base_path := is_pull_through_distribution_marked(distribution):
        return base_path
    return distribution.base_path


def _match_path(queryset, path, field):
    """Return the longest segment-aware path match from a queryset."""
    prefix_field = f"{field}_prefix"
    return (
        queryset.annotate(
            requested_path=Value(path, output_field=TextField()),
            **{prefix_field: Concat(F(field), Value("/"), output_field=TextField())},
        )
        .filter(Q(requested_path=F(field)) | Q(requested_path__startswith=F(prefix_field)))
        .order_by(f"-{field}")
        .first()
    )


def get_pull_through_distribution(path):
    """Find a pull-through distribution using the repaired scheme, then the legacy scheme."""
    distributions = ContainerPullThroughDistribution.objects.all()
    marked = distributions.filter(pulp_labels__has_key=PULL_THROUGH_DISTRIBUTION_LABEL)
    if distribution := _match_path(marked, path, f"pulp_labels__{PULL_THROUGH_DISTRIBUTION_LABEL}"):
        return distribution

    legacy = distributions.exclude(pulp_labels__has_key=PULL_THROUGH_DISTRIBUTION_LABEL)
    return _match_path(legacy, path, "base_path")


def find_container_distribution_overlaps():
    """Return pairs where a container distribution overlaps any distribution."""
    container_ids = set(ContainerDistribution.objects.values_list("pk", flat=True))
    distributions = list(Distribution.objects.order_by("base_path", "pk"))
    by_path = {}
    for distribution in distributions:
        by_path.setdefault(distribution.base_path, []).append(distribution)
    overlaps = []

    for distribution in distributions:
        parts = distribution.base_path.split("/")
        for index in range(1, len(parts)):
            parent_path = "/".join(parts[:index])
            for parent in by_path.get(parent_path, []):
                if parent.pk in container_ids or distribution.pk in container_ids:
                    overlaps.append((parent, distribution))

    return overlaps
