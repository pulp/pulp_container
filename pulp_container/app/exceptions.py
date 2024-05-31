from rest_framework.exceptions import APIException, NotFound, ParseError


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
        super().__init__(
            detail={
                "errors": [
                    {
                        "code": "NAME_UNKNOWN",
                        "message": "Repository not found.",
                        "detail": {"name": name},
                    }
                ]
            }
        )


class RepositoryInvalid(ParseError):
    """Exception to render a 400 with the code 'NAME_INVALID'"""

    def __init__(self, name, message=None):
        """Initialize the exception with the repository name."""
        message = message or "Invalid repository name."
        super().__init__(
            detail={
                "errors": [{"code": "NAME_INVALID", "message": message, "detail": {"name": name}}]
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
                        "message": "Blob not found.",
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
