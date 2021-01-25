from pulpcore.plugin.models import ContentArtifact, CreatedResource, Repository
from pulp_container.app.models import Manifest, Tag


def tag_image(manifest_pk, tag, repository_pk):
    """
    Create a new repository version out of the passed tag name and the manifest.

    If the tag name is already associated with an existing manifest with the same digest,
    no new content is created. Note that a same tag name cannot be used for two different
    manifests. Due to this fact, an old Tag object is going to be removed from
    a new repository version when a manifest contains a digest which is not equal to the
    digest passed with POST request.
    """
    manifest = Manifest.objects.get(pk=manifest_pk)
    artifact = manifest._artifacts.all()[0]

    repository = Repository.objects.get(pk=repository_pk).cast()
    latest_version = repository.latest_version()

    tags_to_remove = Tag.objects.filter(pk__in=latest_version.content.all(), name=tag).exclude(
        tagged_manifest=manifest
    )

    manifest_tag, created = Tag.objects.get_or_create(name=tag, tagged_manifest=manifest)

    if created:
        resource = CreatedResource(content_object=manifest_tag)
        resource.save()

    ContentArtifact.objects.get_or_create(
        artifact=artifact, content=manifest_tag, relative_path=tag
    )

    tags_to_add = Tag.objects.filter(pk=manifest_tag.pk).exclude(
        pk__in=latest_version.content.all()
    )

    with repository.new_version() as repository_version:
        repository_version.remove_content(tags_to_remove)
        repository_version.add_content(tags_to_add)
