from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect
from urllib.parse import urljoin

from pulp_container.app.exceptions import ManifestNotFound
from pulp_container.app.utils import get_accepted_media_types
from pulp_container.constants import BLOB_CONTENT_TYPE, MEDIA_TYPE


class CommonRedirects:
    """
    A class that serves for common redirects which target the content app.
    """

    def __init__(self, distribution, path, request):
        """
        Initialize fields which are required for performing specific redirects.
        """
        self.distribution = distribution
        self.path = path
        self.request = request
        self.path_prefix = (
            f"pulp/container/{request.pulp_domain.name}"
            if settings.DOMAIN_ENABLED
            else "pulp/container"
        )

    def redirect_to_content_app(self, content_type, content_id):
        """
        Redirect to the content app.
        """

        return self.distribution.redirect_to_content_app(
            urljoin(
                settings.CONTENT_ORIGIN,
                f"/{self.path_prefix}/{self.path}/{content_type}/{content_id}",
            )
        )

    def issue_manifest_redirect(self, manifest):
        """
        Issue a redirect for the passed manifest.
        """
        return self.redirect_to_content_app("manifests", manifest.digest)

    def issue_tag_redirect(self, tag):
        """
        Issue a redirect for the passed tag.
        """
        manifest_media_type = tag.tagged_manifest.media_type
        if (
            manifest_media_type not in get_accepted_media_types(self.request.headers)
            and manifest_media_type != MEDIA_TYPE.MANIFEST_V1
        ):
            raise ManifestNotFound(reference=tag.name)

        return self.redirect_to_content_app("manifests", tag.name)


class FileStorageRedirects(CommonRedirects):
    """
    A class which contains methods used for redirecting to the default django's file storage.
    """

    def issue_blob_redirect(self, blob):
        """
        Issue a redirect for the passed blob.
        """
        return self.redirect_to_content_app("blobs", blob.digest)


class S3StorageRedirects(CommonRedirects):
    """
    A class that implements methods for the direct retrieval of manifest objects.
    """

    def issue_blob_redirect(self, blob):
        """
        Redirect to the passed blob or stream content when an associated artifact is not present.
        """
        try:
            artifact = blob._artifacts.get()
        except ObjectDoesNotExist:
            return self.redirect_to_content_app("blobs", blob.digest)

        return self.redirect_to_object_storage(artifact, BLOB_CONTENT_TYPE)

    def redirect_to_object_storage(self, artifact, return_media_type):
        """
        Redirect to the passed artifact's file stored in the S3 storage.
        """
        filename = f"sha256:{artifact.sha256}"
        parameters = {
            "ResponseContentType": return_media_type,
            "ResponseContentDisposition": f"attachment;filename={filename}",
        }
        content_url = artifact.file.storage.url(
            artifact.file.name, parameters=parameters, http_method=self.request.method
        )
        return redirect(content_url)


class AzureStorageRedirects(S3StorageRedirects):
    """
    A class that implements methods for the direct retrieval of manifest objects.
    """

    def redirect_to_object_storage(self, artifact, return_media_type):
        """
        Redirect to the passed artifact's file stored in the Azure storage.
        """
        filename = f"sha256:{artifact.sha256}"
        parameters = {
            "content_type": return_media_type,
            "content_disposition": f"attachment;filename={filename}",
        }
        content_url = artifact.file.storage.url(artifact.file.name, parameters=parameters)
        return redirect(content_url)
