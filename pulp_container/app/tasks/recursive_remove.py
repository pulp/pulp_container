from django.db.models import Q
from pulpcore.plugin.models import Content, Repository

from pulp_container.app.models import (
    Blob,
    Manifest,
    MEDIA_TYPE,
    Tag,
)


def recursive_remove_content(repository_pk, content_units):
    """
    Create a new repository version by recursively removing content.

    For each unit that is specified, we also need to remove related content,
    unless that content is also related to content that will remain in the
    repository. For example, if a manifest-list is specified, we need to remove
    all referenced manifests unless those manifests are referenced by a
    manifest-list that will stay in the repository.

    For each content type, we identify 3 categories:
    1. must_remain: These content units are referenced by content units that will not be removed
    2. to_remove: These content units are either explicity given by the user,
       or they are referenced by the content explicity given, and they are not in must_remain.
    3. to_remain: Content in the repo that is not in to_remove. This category
       is used to determine must_remain of lower heirarchy content.


    Args:
        repository_pk (int): The primary key for a Repository for which a new Repository Version
            should be created.
        content_units (list): List of PKs for :class:`~pulpcore.app.models.Content` that
            should be removed from the Repository.

    """
    repository = Repository.objects.get(pk=repository_pk).cast()
    latest_version = repository.latest_version()
    latest_content = latest_version.content.all() if latest_version else Content.objects.none()
    if "*" in content_units:
        with repository.new_version() as new_version:
            new_version.remove_content(latest_content)
    else:
        tags_in_repo = Q(pk__in=latest_content.filter(pulp_type=Tag.get_pulp_type()))
        manifests_in_repo = Q(pk__in=latest_content.filter(pulp_type=Manifest.get_pulp_type()))
        user_provided_content = Q(pk__in=content_units)
        type_manifest_list = Q(media_type__in=[MEDIA_TYPE.MANIFEST_LIST, MEDIA_TYPE.INDEX_OCI])
        manifest_media_types = [
            MEDIA_TYPE.MANIFEST_V1,
            MEDIA_TYPE.MANIFEST_V2,
            MEDIA_TYPE.MANIFEST_OCI,
        ]
        type_manifest = Q(media_type__in=manifest_media_types)
        blobs_in_repo = Q(pk__in=latest_content.filter(pulp_type=Blob.get_pulp_type()))

        # Tags do not have must_remain because they are the highest level content.
        tags_to_remove = Tag.objects.filter(user_provided_content & tags_in_repo)
        tags_to_remain = Tag.objects.filter(tags_in_repo).exclude(pk__in=tags_to_remove)
        tagged_manifests_must_remain = Q(
            pk__in=tags_to_remain.values_list("tagged_manifest", flat=True)
        )
        tagged_manifests_to_remove = Q(
            pk__in=tags_to_remove.values_list("tagged_manifest", flat=True)
        )

        manifest_lists_must_remain = Manifest.objects.filter(
            manifests_in_repo & tagged_manifests_must_remain & type_manifest_list
        )
        manifest_lists_to_remove = (
            Manifest.objects.filter(user_provided_content | tagged_manifests_to_remove)
            .filter(type_manifest_list & manifests_in_repo)
            .exclude(pk__in=manifest_lists_must_remain)
        )

        manifest_lists_to_remain = Manifest.objects.filter(
            manifests_in_repo & type_manifest_list
        ).exclude(pk__in=manifest_lists_to_remove)

        listed_manifests_must_remain = Q(
            pk__in=manifest_lists_to_remain.values_list("listed_manifests", flat=True)
        )
        manifests_must_remain = Manifest.objects.filter(
            tagged_manifests_must_remain | listed_manifests_must_remain
        ).filter(type_manifest & manifests_in_repo)

        listed_manifests_to_remove = Q(
            pk__in=manifest_lists_to_remove.values_list("listed_manifests", flat=True)
        )
        manifests_to_remove = (
            Manifest.objects.filter(
                user_provided_content | listed_manifests_to_remove | tagged_manifests_to_remove
            )
            .filter(type_manifest & manifests_in_repo)
            .exclude(pk__in=manifests_must_remain)
        )

        manifests_to_remain = Manifest.objects.filter(manifests_in_repo & type_manifest).exclude(
            pk__in=manifests_to_remove
        )

        listed_blobs_must_remain = Q(
            pk__in=manifests_to_remain.values_list("blobs", flat=True)
        ) | Q(pk__in=manifests_to_remain.values_list("config_blob", flat=True))
        listed_blobs_to_remove = Q(pk__in=manifests_to_remove.values_list("blobs", flat=True)) | Q(
            pk__in=manifests_to_remove.values_list("config_blob", flat=True)
        )

        blobs_to_remove = (
            Blob.objects.filter(user_provided_content | listed_blobs_to_remove)
            .filter(blobs_in_repo)
            .exclude(listed_blobs_must_remain)
        )

        with repository.new_version() as new_version:
            new_version.remove_content(tags_to_remove)
            new_version.remove_content(manifest_lists_to_remove)
            new_version.remove_content(manifests_to_remove)
            new_version.remove_content(blobs_to_remove)
