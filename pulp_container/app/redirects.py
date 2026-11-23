from urllib.parse import urljoin

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect

from pulpcore.plugin.util import get_direct_storage_url

from pulp_container.constants import BLOB_CONTENT_TYPE


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


class StorageRedirects(CommonRedirects):
    """
    Redirect blobs to storage when the Domain supports direct URLs.
    """

    def issue_blob_redirect(self, blob):
        """
        Redirect to the passed blob or stream content when an associated artifact is not present.
        """
        try:
            artifact = blob._artifacts.get()
        except ObjectDoesNotExist:
            return self.redirect_to_content_app("blobs", blob.digest)

        content_url = get_direct_storage_url(
            artifact.file,
            headers={
                "Content-Type": BLOB_CONTENT_TYPE,
                "Content-Disposition": f"attachment;filename=sha256:{artifact.sha256}",
            },
            http_method=self.request.method,
        )
        if content_url is None:
            return self.redirect_to_content_app("blobs", blob.digest)
        return redirect(content_url)
