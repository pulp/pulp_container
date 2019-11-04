from pulp_docker.app.models import DockerRepository, Tag


def untag_image(tag, repository_pk):
    """
    Create a new repository version without a specified manifest's tag name.
    """
    repository = DockerRepository.objects.get(pk=repository_pk)
    latest_version = repository.latest_version()

    tags_in_latest_repository = latest_version.content.filter(
        pulp_type="docker.tag"
    )

    tags_to_remove = Tag.objects.filter(
        pk__in=tags_in_latest_repository,
        name=tag
    )

    with repository.new_version() as repository_version:
        repository_version.remove_content(tags_to_remove)
