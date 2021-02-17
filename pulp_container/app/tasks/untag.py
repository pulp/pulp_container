from pulpcore.plugin.models import Repository
from pulp_container.app.models import Tag


def untag_image(tag, repository_pk):
    """
    Create a new repository version without a specified manifest's tag name.
    """
    repository = Repository.objects.get(pk=repository_pk).cast()
    latest_version = repository.latest_version()

    tags_in_latest_repository = latest_version.content.filter(pulp_type=Tag.get_pulp_type())

    tags_to_remove = Tag.objects.filter(pk__in=tags_in_latest_repository, name=tag)

    with repository.new_version() as repository_version:
        repository_version.remove_content(tags_to_remove)
