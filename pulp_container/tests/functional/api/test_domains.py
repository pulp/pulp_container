import pytest
import uuid
from subprocess import CalledProcessError
from pulp_container.tests.functional.constants import (
    REGISTRY_V2_REPO_PULP,
    PULP_FIXTURE_1,
    PULP_HELLO_WORLD_REPO,
)


@pytest.fixture
def cdomain_factory(domain_factory, pulpcore_bindings):
    domains = []

    def _domain_factory(*args, **kwargs):
        domain = domain_factory(*args, **kwargs)
        domains.append(domain)
        return domain

    yield _domain_factory

    for domain in domains:
        guards = pulpcore_bindings.ContentguardsContentRedirectApi.list(pulp_domain=domain.name)
        for guard in guards.results:
            pulpcore_bindings.ContentguardsContentRedirectApi.delete(guard.pulp_href)


def test_push_in_domain(
    container_bindings, cdomain_factory, local_registry, registry_client, add_to_cleanup
):
    # permissions are wrong,
    remote_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
    registry_client.pull(remote_path)

    domain = cdomain_factory()
    local_path = f"{domain.name}/{uuid.uuid4()}:manifest_a"
    local_registry.tag_and_push(remote_path, local_path)

    repo_name = local_path.split("/")[1].split(":")[0]
    # Test that distribution is created in correct domain
    results = container_bindings.DistributionsContainerApi.list(name=repo_name)
    assert len(results.results) == 0
    results = container_bindings.DistributionsContainerApi.list(
        name=repo_name, pulp_domain=domain.name
    )
    assert len(results.results) == 1
    distro = results.results[0]
    assert distro.base_path == repo_name
    assert local_path.split(":")[0] in distro.registry_path
    namespace = container_bindings.PulpContainerNamespacesApi.read(distro.namespace)
    add_to_cleanup(container_bindings.PulpContainerNamespacesApi, namespace.pulp_href)
    assert namespace.name == repo_name


def test_pull_in_domain(
    cdomain_factory,
    local_registry,
    container_repository_factory,
    container_remote_factory,
    container_sync,
    container_distribution_factory,
    tmp_path,
):
    domain = cdomain_factory()
    repo = container_repository_factory(pulp_domain=domain.name)
    remote = container_remote_factory(pulp_domain=domain.name)
    container_sync(repo, remote)
    distribution = container_distribution_factory(
        repository=repo.pulp_href, pulp_domain=domain.name
    )

    local_path = f"{domain.name}/{distribution.base_path}"
    local_registry.pull(local_path)

    # Test file storage domain at custom MEDIA_ROOT
    domain = cdomain_factory(
        storage_class="pulpcore.app.models.storage.FileSystem",
        storage_settings={"MEDIA_ROOT": str(tmp_path)},
    )
    repo = container_repository_factory(pulp_domain=domain.name)
    remote = container_remote_factory(pulp_domain=domain.name)
    container_sync(repo, remote)
    distribution = container_distribution_factory(
        repository=repo.pulp_href, pulp_domain=domain.name
    )

    local_path = f"{domain.name}/{distribution.base_path}"
    local_registry.pull(local_path)


def test_domain_permissions(
    cdomain_factory,
    container_bindings,
    local_registry,
    registry_client,
    gen_user,
    add_to_cleanup,
    monitor_task,
    pulp_settings,
):
    if pulp_settings.TOKEN_AUTH_DISABLED:
        pytest.skip("Domain permissions cannot be tested when token authentication is disabled")

    domain = cdomain_factory()
    user_creator = gen_user(
        domain_roles=[("container.containernamespace_creator", domain.pulp_href)]
    )
    user_reader = gen_user(
        domain_roles=[("container.containernamespace_consumer", domain.pulp_href)]
    )
    user_helpless = gen_user()

    # create a push repo
    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_d"
    registry_client.pull(image_path)
    repo_name = str(uuid.uuid4())
    local_path = f"{domain.name}/{repo_name}:manifest_a"
    with user_creator:
        local_registry.tag_and_push(image_path, local_path)
        namespace = container_bindings.PulpContainerNamespacesApi.list(
            name=repo_name, pulp_domain=domain.name
        ).results[0]
    add_to_cleanup(container_bindings.PulpContainerNamespacesApi, namespace.pulp_href)

    with user_reader, pytest.raises(CalledProcessError):
        local_registry.tag_and_push(local_path, f"{domain.name}/{repo_name}:manifest_b")

    with user_helpless, pytest.raises(CalledProcessError):
        local_registry.tag_and_push(local_path, f"{domain.name}/{repo_name}:manifest_b")

    # Try pull
    with user_reader:
        local_registry.pull(local_path)

    with user_helpless:
        local_registry.pull(local_path)

    # Try pull with private distribution
    distribution = container_bindings.DistributionsContainerApi.list(
        name=repo_name, pulp_domain=domain.name
    ).results[0]
    task = container_bindings.DistributionsContainerApi.partial_update(
        distribution.pulp_href, {"private": True}
    )
    monitor_task(task.task)

    with user_reader:
        local_registry.pull(local_path)

    with user_helpless, pytest.raises(CalledProcessError):
        local_registry.pull(local_path)


def test_cross_domain_blob_mount(
    cdomain_factory,
    container_bindings,
    local_registry,
    registry_client,
    add_to_cleanup,
    pulp_settings,
):
    if pulp_settings.TOKEN_AUTH_DISABLED:
        pytest.skip("Cannot test blob mounting without token authentication.")

    def mount_blob(blob, source, dest):
        mount_path = f"/v2/{dest}/blobs/uploads/?from={source}&mount={blob.digest}"
        response, auth = local_registry.get_response("POST", mount_path)
        return response, auth

    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
    registry_client.pull(image_path)

    domain1 = cdomain_factory()
    domain2 = cdomain_factory()
    source_repo = str(uuid.uuid4())
    dest_repo = str(uuid.uuid4())

    local_repo = f"{domain1.name}/{source_repo}"
    local_registry.tag_and_push(image_path, local_repo)
    repository = container_bindings.RepositoriesContainerPushApi.list(
        name=source_repo, pulp_domain=domain1.name
    ).results[0]
    blobs = container_bindings.ContentBlobsApi.list(
        repository_version=repository.latest_version_href
    ).results
    distribution = container_bindings.DistributionsContainerApi.list(
        name=source_repo, pulp_domain=domain1.name
    ).results[0]
    add_to_cleanup(container_bindings.PulpContainerNamespacesApi, distribution.namespace)

    # Try to mount blobs from domain1 to domain2
    for blob in blobs:
        response, auth = mount_blob(blob, local_repo, f"{domain2.name}/{dest_repo}")
        assert response.status_code == 400
        assert response.body == "Cross-domain blob mounting is not allowed."


@pytest.mark.parallel
def test_cross_domain_pulp_apis(
    cdomain_factory,
    container_bindings,
    container_signing_service,
    gen_object_with_cleanup,
    container_repository_factory,
    container_remote_factory,
    container_sync,
    pulpcore_bindings,
    file_repository_factory,
    tmp_path,
):
    domain1 = cdomain_factory()
    domain2 = cdomain_factory()

    # Creating pull-through distribution with pull-through remote
    pt_remote = gen_object_with_cleanup(
        container_bindings.RemotesPullThroughApi,
        {
            "name": str(uuid.uuid4()),
            "url": "https://ghcr.io",
        },
        pulp_domain=domain1.name,
    )
    with pytest.raises(container_bindings.ApiException) as e:
        container_bindings.DistributionsPullThroughApi.create(
            {
                "name": str(uuid.uuid4()),
                "base_path": str(uuid.uuid4()),
                "remote": pt_remote.pulp_href,
            },
            pulp_domain=domain2.name,
        )
    assert e.value.status == 400
    assert f"Objects must all be a part of the {domain2.name} domain." in e.value.body

    # Create repository with manifest signing service (signing services are domain agnostic)
    assert "default" in container_signing_service.pulp_href  # They live in the default domain
    repo = container_repository_factory(
        name=str(uuid.uuid4()),
        manifest_signing_service=container_signing_service.pulp_href,
        pulp_domain=domain2.name,
    )
    assert repo.manifest_signing_service == container_signing_service.pulp_href

    remote = container_remote_factory(pulp_domain=domain2.name)
    container_sync(repo, remote)
    content_hrefs = [
        c.pulp_href for c in pulpcore_bindings.ContentApi.list(pulp_domain=domain2.name).results
    ]

    # Add/remove content to repository
    repo_1 = container_repository_factory(pulp_domain=domain1.name)
    with pytest.raises(container_bindings.ApiException) as e:
        container_bindings.RepositoriesContainerApi.add(
            repo_1.pulp_href,
            {"content_units": content_hrefs},
        )
    assert e.value.status == 400
    assert f"Content units are not a part of the current domain {domain1.name}" in e.value.body
    with pytest.raises(container_bindings.ApiException) as e:
        container_bindings.RepositoriesContainerApi.remove(
            repo_1.pulp_href,
            {"content_units": content_hrefs},
        )
    assert e.value.status == 400
    assert f"Content units are not a part of the current domain {domain1.name}" in e.value.body

    # Build image with file repository version
    file_repo = file_repository_factory()  # default domain
    containerfile = tmp_path / "Containerfile"
    containerfile.write_bytes(b"FROM quay.io/quay/busybox:latest")
    with pytest.raises(container_bindings.ApiException) as e:
        container_bindings.RepositoriesContainerApi.build_image(
            repo.pulp_href,
            containerfile=str(containerfile),
            build_context=file_repo.latest_version_href,
        )
    assert e.value.status == 400
    assert f"Objects must all be a part of the {domain2.name} domain." in e.value.body

    # Copy manifests with source repository/version
    with pytest.raises(container_bindings.ApiException) as e:
        container_bindings.RepositoriesContainerApi.copy_manifests(
            repo_1.pulp_href,
            {"source_repository": repo.pulp_href},
        )
    assert e.value.status == 400
    assert f"Objects must all be a part of the {domain1.name} domain." in e.value.body
    with pytest.raises(container_bindings.ApiException) as e:
        container_bindings.RepositoriesContainerApi.copy_manifests(
            repo_1.pulp_href,
            {"source_repository_version": repo.latest_version_href},
        )
    assert e.value.status == 400
    assert f"Objects must all be a part of the {domain1.name} domain." in e.value.body
    # Copy tags with source repository/version
    with pytest.raises(container_bindings.ApiException) as e:
        container_bindings.RepositoriesContainerApi.copy_tags(
            repo_1.pulp_href,
            {"source_repository": repo.pulp_href},
        )
    assert e.value.status == 400
    assert f"Objects must all be a part of the {domain1.name} domain." in e.value.body
    with pytest.raises(container_bindings.ApiException) as e:
        container_bindings.RepositoriesContainerApi.copy_tags(
            repo_1.pulp_href,
            {"source_repository_version": repo.latest_version_href},
        )
    assert e.value.status == 400
    assert f"Objects must all be a part of the {domain1.name} domain." in e.value.body

    # Sign images with manifest signing service and tags
    container_bindings.RepositoriesContainerApi.sign(
        repo.pulp_href,
        {
            "manifest_signing_service": container_signing_service.pulp_href,
            "future_base_path": "test",
        },
    )
    container_bindings.RepositoriesContainerApi.sign(
        repo_1.pulp_href,
        {
            "manifest_signing_service": container_signing_service.pulp_href,
            "future_base_path": "test",
        },
    )


@pytest.mark.parallel
def test_domain_content_replication(
    cdomain_factory,
    bindings_cfg,
    pulp_settings,
    pulpcore_bindings,
    container_bindings,
    container_sync,
    container_repository_factory,
    container_remote_factory,
    container_distribution_factory,
    monitor_task_group,
    gen_object_with_cleanup,
    add_to_cleanup,
):
    """Test replication feature through the usage of domains."""
    # Set up source domain to replicate from
    source_domain = cdomain_factory()
    for name in [PULP_FIXTURE_1, PULP_HELLO_WORLD_REPO]:
        repo = container_repository_factory(pulp_domain=source_domain.name)
        remote = container_remote_factory(pulp_domain=source_domain.name, upstream_name=name)
        container_sync(repo, remote)
        container_distribution_factory(repository=repo.pulp_href, pulp_domain=source_domain.name)

    # Create the replica domain
    replica_domain = cdomain_factory()
    upstream_pulp_body = {
        "name": str(uuid.uuid4()),
        "base_url": bindings_cfg.host,
        "api_root": pulp_settings.API_ROOT,
        "domain": source_domain.name,
        "username": bindings_cfg.username,
        "password": bindings_cfg.password,
        "tls_validation": False,
    }
    upstream_pulp = gen_object_with_cleanup(
        pulpcore_bindings.UpstreamPulpsApi, upstream_pulp_body, pulp_domain=replica_domain.name
    )
    # Run the replicate task and assert that all tasks successfully complete.
    response = pulpcore_bindings.UpstreamPulpsApi.replicate(upstream_pulp.pulp_href)
    monitor_task_group(response.task_group)

    counts = {}
    for api_client in (
        container_bindings.ContentManifestsApi,
        container_bindings.ContentBlobsApi,
        container_bindings.ContentTagsApi,
        container_bindings.RepositoriesContainerApi,
        container_bindings.RemotesContainerApi,
        container_bindings.DistributionsContainerApi,
    ):
        source_result = api_client.list(pulp_domain=source_domain.name)
        replica_result = api_client.list(pulp_domain=replica_domain.name)
        counts[api_client] = (source_result.count, replica_result.count)
        for item in replica_result.results:
            add_to_cleanup(api_client, item.pulp_href)

    assert all(x[0] == x[1] for x in counts.values()), f"Replica had differing counts {counts}"
