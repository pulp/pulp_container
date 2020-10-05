# -*- coding: utf-8 -*-
from django.contrib import admin

from pulpcore.plugin.admin import BaseModelAdmin, PulpModelAdmin

from .models import (
    Blob,
    Manifest,
    BlobManifest,
    ManifestListManifest,
    Tag,
    ContainerRepository,
    ContainerPushRepository,
    ContainerRemote,
    ContainerDistribution,
    Upload,
    ContentRedirectContentGuard,
)


@admin.register(Blob)
class BlobAdmin(PulpModelAdmin):
    list_display = (
        "pulp_id",
        "pulp_created",
        "pulp_last_updated",
        "pulp_type",
        "upstream_id",
        "digest",
        "media_type",
    )
    list_filter = ("pulp_created", "pulp_last_updated")


@admin.register(Manifest)
class ManifestAdmin(PulpModelAdmin):
    list_display = (
        "pulp_id",
        "pulp_created",
        "pulp_last_updated",
        "pulp_type",
        "upstream_id",
        "digest",
        "schema_version",
        "media_type",
        "config_blob",
    )
    list_filter = ("pulp_created", "pulp_last_updated", "config_blob")
    raw_id_fields = ("blobs", "listed_manifests")


@admin.register(BlobManifest)
class BlobManifestAdmin(BaseModelAdmin):
    list_display = ("id", "manifest", "manifest_blob")
    list_filter = ("manifest", "manifest_blob")


@admin.register(ManifestListManifest)
class ManifestListManifestAdmin(BaseModelAdmin):
    list_display = (
        "id",
        "architecture",
        "os",
        "os_version",
        "os_features",
        "features",
        "variant",
        "image_manifest",
        "manifest_list",
    )
    list_filter = ("image_manifest", "manifest_list")


@admin.register(Tag)
class TagAdmin(PulpModelAdmin):
    list_display = (
        "pulp_id",
        "pulp_created",
        "pulp_last_updated",
        "pulp_type",
        "upstream_id",
        "name",
        "tagged_manifest",
    )
    list_filter = ("pulp_created", "pulp_last_updated", "tagged_manifest")
    search_fields = ("name",)


@admin.register(ContainerRepository)
class ContainerRepositoryAdmin(PulpModelAdmin):
    list_display = (
        "pulp_id",
        "pulp_created",
        "pulp_last_updated",
        "pulp_type",
        "name",
        "description",
        "next_version",
        "remote",
    )
    list_filter = ("pulp_created", "pulp_last_updated")
    search_fields = ("name",)


@admin.register(ContainerPushRepository)
class ContainerPushRepositoryAdmin(PulpModelAdmin):
    list_display = (
        "pulp_id",
        "pulp_created",
        "pulp_last_updated",
        "pulp_type",
        "name",
        "description",
        "next_version",
        "remote",
    )
    list_filter = ("pulp_created", "pulp_last_updated")
    search_fields = ("name",)


@admin.register(ContainerRemote)
class ContainerRemoteAdmin(PulpModelAdmin):
    list_display = (
        "pulp_id",
        "pulp_created",
        "pulp_last_updated",
        "pulp_type",
        "name",
        "url",
        "ca_cert",
        "client_cert",
        "client_key",
        "tls_validation",
        "username",
        "password",
        "proxy_url",
        "download_concurrency",
        "policy",
        "upstream_name",
        "include_foreign_layers",
        "include_tags",
        "exclude_tags",
    )
    list_filter = (
        "pulp_created",
        "pulp_last_updated",
        "tls_validation",
        "include_foreign_layers",
    )
    search_fields = ("name",)


@admin.register(ContainerDistribution)
class ContainerDistributionAdmin(PulpModelAdmin):
    list_display = (
        "pulp_id",
        "pulp_created",
        "pulp_last_updated",
        "pulp_type",
        "name",
        "base_path",
        "content_guard",
        "remote",
        "repository",
        "repository_version",
    )
    list_filter = (
        "pulp_created",
        "pulp_last_updated",
        "repository",
        "repository_version",
    )
    search_fields = ("name",)


@admin.register(Upload)
class UploadAdmin(PulpModelAdmin):
    list_display = (
        "pulp_id",
        "pulp_created",
        "pulp_last_updated",
        "repository",
        "offset",
        "file",
        "size",
        "md5",
        "sha1",
        "sha224",
        "sha256",
        "sha384",
        "sha512",
    )
    list_filter = ("pulp_created", "pulp_last_updated", "repository")


@admin.register(ContentRedirectContentGuard)
class ContentRedirectContentGuardAdmin(PulpModelAdmin):
    list_display = (
        "pulp_id",
        "pulp_created",
        "pulp_last_updated",
        "pulp_type",
        "name",
        "description",
        "shared_secret",
    )
    list_filter = ("pulp_created", "pulp_last_updated")
    search_fields = ("name",)
