from rest_framework.exceptions import APIException, NotFound, ParseError

from pulpcore.plugin.exceptions import PulpException


class BadGateway(APIException):
    status_code = 502
    default_detail = "Invalid response received from the upstream."
    default_code = "BAD_GATEWAY"


class GatewayTimeout(APIException):
    status_code = 504
    default_detail = "Response from the upstream timed out."
    default_code = "GATEWAY_TIMEOUT"


class RepositoryNotFound(NotFound):
    """Exception to render a 404 with the code 'NAME_UNKNOWN'"""

    def __init__(self, name):
        """Initialize the exception with the repository name."""
        from pulp_container.app.utils import get_full_path

        super().__init__(
            detail={
                "errors": [
                    {
                        "code": "NAME_UNKNOWN",
                        "message": "Repository not found.",
                        "detail": {"name": get_full_path(name)},
                    }
                ]
            }
        )


class RepositoryInvalid(ParseError):
    """Exception to render a 400 with the code 'NAME_INVALID'"""

    def __init__(self, name, message=None):
        """Initialize the exception with the repository name."""
        from pulp_container.app.utils import get_full_path

        message = message or "Invalid repository name."
        super().__init__(
            detail={
                "errors": [
                    {
                        "code": "NAME_INVALID",
                        "message": message,
                        "detail": {"name": get_full_path(name)},
                    }
                ]
            }
        )


class BlobNotFound(NotFound):
    """Exception to render a 404 with the code 'BLOB_UNKNOWN'"""

    def __init__(self, digest):
        """Initialize the exception with the blob digest."""
        super().__init__(
            detail={
                "errors": [
                    {
                        "code": "BLOB_UNKNOWN",
                        "message": "Blob not found, hello!?",
                        "detail": {"digest": digest},
                    }
                ]
            }
        )


class BlobInvalid(ParseError):
    """Exception to render a 400 with the code 'BLOB_UNKNOWN'"""

    def __init__(self, digest):
        """Initialize the exception with the blob digest."""
        super().__init__(
            detail={
                "errors": [
                    {
                        "code": "BLOB_UNKNOWN",
                        "message": "blob unknown to registry",
                        "detail": {"digest": digest},
                    }
                ]
            }
        )


class BlobUploadUnknown(NotFound):
    """Exception to render a 404 with the code 'BLOB_UPLOAD_UNKNOWN'"""

    def __init__(self, uuid):
        """Initialize the exception with the upload uuid."""
        super().__init__(
            detail={
                "errors": [
                    {
                        "code": "BLOB_UPLOAD_UNKNOWN",
                        "message": "blob upload unknown to registry",
                        "detail": {"uuid": uuid},
                    }
                ]
            }
        )


class ManifestNotFound(NotFound):
    """Exception to render a 404 with the code 'MANIFEST_UNKNOWN'"""

    def __init__(self, reference):
        """Initialize the exception with the manifest reference."""
        super().__init__(
            detail={
                "errors": [
                    {
                        "code": "MANIFEST_UNKNOWN",
                        "message": "Manifest not found.",
                        "detail": {"reference": reference},
                    }
                ]
            }
        )


class ManifestInvalid(ParseError):
    """Exception to render a 400 with the code 'MANIFEST_INVALID'"""

    def __init__(self, digest, reason=None):
        """Initialize the exception with the manifest digest."""
        super().__init__(
            detail={
                "errors": [
                    {
                        "code": "MANIFEST_INVALID",
                        "message": reason or "manifest invalid",
                        "detail": {"digest": digest},
                    }
                ]
            }
        )


class ManifestSignatureInvalid(ParseError):
    """An exception to render an HTTP 400 response with the code 'SIGNATURE_INVALID'."""

    def __init__(self, digest):
        """Initialize the exception with the digest of a signed manifest."""
        super().__init__(
            detail={
                "errors": [
                    {
                        "code": "SIGNATURE_INVALID",
                        "message": "signature invalid",
                        "detail": {"manifest_digest": digest},
                    }
                ]
            }
        )


class TaskResourceNotFound(PulpException):
    """Exception to signal that a resource a task depends on no longer exists.

    Tasks look up their arguments' referenced objects by pk. If that object was
    deleted between dispatch and execution (e.g. by a racing delete), a bare Django
    DoesNotExist is not a PulpException, which pulpcore's task executor logs as
    deprecated and will sanitize away in a future release. Raise this instead so the
    real reason is preserved on the task result.
    """

    error_code = "CON0001"

    def __init__(self, message):
        """Initialize the exception with a description of the missing resource."""
        self.message = message

    def __str__(self):
        return self.message


class InvalidRequest(ParseError):
    """An exception to render an HTTP 400 response."""

    def __init__(self, message):
        """Initialize the exception with the digest of a signed manifest."""
        message = message or "Invalid request."
        super().__init__(
            detail={
                "errors": [
                    {
                        "code": "INVALID_REQUEST",
                        "message": message,
                        "detail": {},
                    }
                ]
            }
        )
