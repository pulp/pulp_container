"""Tests that CRUD distributions."""

import pytest
import uuid


@pytest.mark.parallel
def test_crud_distributions(
    container_bindings, container_distribution_factory, add_to_cleanup, monitor_task
):
    """Test CRUD distributions."""
    # Create a distribution.
    name = str(uuid.uuid4())
    base_path = name.replace("-", "/")
    distribution = container_distribution_factory(name=name, base_path=base_path)
    assert base_path == distribution.base_path
    assert name == distribution.name

    # assert that namespace was created and it matches first component of base_path
    assert (
        container_bindings.PulpContainerNamespacesApi.read(distribution.namespace).name
        == base_path.split("/")[0]
    )
    add_to_cleanup(container_bindings.PulpContainerNamespacesApi, distribution.namespace)

    # Create a second distribution with the same name.
    with pytest.raises(container_bindings.ApiException):
        container_distribution_factory(name=name)

    # Update the distribution.
    new_base_path = str(uuid.uuid4()).replace("-", "/")
    response = container_bindings.DistributionsContainerApi.partial_update(
        distribution.pulp_href, {"base_path": new_base_path}
    )
    monitor_task(response.task)
    distribution = container_bindings.DistributionsContainerApi.read(distribution.pulp_href)
    assert new_base_path == distribution.base_path

    assert (
        container_bindings.PulpContainerNamespacesApi.read(distribution.namespace).name
        == new_base_path.split("/")[0]
    )
    add_to_cleanup(container_bindings.PulpContainerNamespacesApi, distribution.namespace)

    # Delete the distribution.
    delete_response = container_bindings.DistributionsContainerApi.delete(distribution.pulp_href)
    monitor_task(delete_response.task)
    with pytest.raises(container_bindings.ApiException):
        container_bindings.DistributionsContainerApi.read(distribution.pulp_href)
