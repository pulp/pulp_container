import jwt

from django.conf import settings
from django.contrib.auth.models import AnonymousUser, User

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import BasePermission, SAFE_METHODS


class HasNoScope(Exception):
    """
    The scope could not be determined from the referenced resource.
    """


class RepositoryScope:
    """
    A data class for repositories' scope.
    """

    def __init__(self, path, method):
        """
        Initialize common scope fields.
        """
        self.resource_type = "repository"
        self.name = path
        if method in SAFE_METHODS:
            self.action = "pull"
        else:
            self.action = "push"


class CatalogScope:
    """
    A data class for the catalog endpoint's scope.
    """

    def __init__(self):
        """
        Initialize common scope fields.
        """
        self.resource_type = "registry"
        self.name = "catalog"
        self.action = "*"


class ScopeFactory:
    """
    A factory class that initializes the known scopes required for further evaluation.
    """

    @staticmethod
    def from_request(request):
        """
        Return an initialized scope object based on the passed request's data.
        """
        path = request.resolver_match.kwargs.get("path", "")
        if path:
            return RepositoryScope(path, request.method)
        elif request.path == "/v2/_catalog":
            return CatalogScope()
        elif request.path == "/v2/":
            raise HasNoScope()


class TokenAuthentication(BaseAuthentication):
    """
    Token based authentication for Container Registry.
    Clients should authenticate by passing the token key in the "Authorization"
    HTTP header, prepended with the string "Bearer ".  For example:
        Authorization: Bearer 401f7ac837da42b97f613d789819ff93537bee6a
    """

    keyword = "Bearer"

    def authenticate(self, request):
        """
        Check that the provided Bearer token specifies access.
        """
        if settings.get("TOKEN_AUTH_DISABLED", False):
            return (AnonymousUser(), True)

        try:
            authorization_header = request.headers["Authorization"]
        except KeyError:
            # No authorization
            return None
        if not authorization_header.lower().startswith(self.keyword.lower() + " "):
            # Not our type of authorization
            return None
        token = authorization_header[len(self.keyword) + 1 :]
        try:
            decoded_token = _decode_token(token, request)
        except jwt.exceptions.InvalidTokenError:
            raise AuthenticationFailed(
                detail="Access to the requested resource is not authorized. "
                "The provided Bearer token is invalid.",
            )

        username = decoded_token.get("sub")
        if username:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                raise AuthenticationFailed("No such user")
        else:
            user = AnonymousUser()
        return (user, decoded_token)

    def authenticate_header(self, request):
        """
        Initialize the Wwww-Authenticate header.

        For example, a created string will be the in following format:
        realm="http://localhost:123/token",service="docker.io",scope="repository:app:push"
        and will be used in the header.
        """
        realm = settings.TOKEN_SERVER
        authenticate_string = f'{self.keyword} realm="{realm}",service="{request.get_host()}"'

        try:
            scope = ScopeFactory.from_request(request)
            authenticate_string += f",scope={scope.resource_type}:{scope.name}:{scope.action}"
        except HasNoScope:
            pass

        return authenticate_string


def _decode_token(encoded_token, request):
    """
    Decode the token and verify the signature with a public key.

    If the token could not be decoded with a success, a client does not have
    permission to operate with a registry.
    """
    JWT_DECODER_CONFIG = {
        "algorithms": [settings.TOKEN_SIGNATURE_ALGORITHM],
        "issuer": settings.TOKEN_SERVER,
        "audience": request.get_host(),
    }
    with open(settings.PUBLIC_KEY_PATH, "rb") as public_key:
        decoded_token = jwt.decode(encoded_token, public_key.read(), **JWT_DECODER_CONFIG)
    return decoded_token


class TokenPermission(BasePermission):
    """
    Permission class to determine permissions based on the scope of a token.
    """

    message = "Access to the requested resource is not authorized."

    def has_permission(self, request, view):
        """
        Decide upon permission based on token
        """
        decoded_token = request.auth
        if decoded_token is True:
            return True
        elif decoded_token is None:
            return False

        try:
            scope = ScopeFactory.from_request(request)
        except HasNoScope:
            return is_requesting_root_endpoint(decoded_token)
        else:
            return contains_accessible_actions(decoded_token, scope)


def is_requesting_root_endpoint(decoded_token):
    """
    Returns True if no access type was detected.
    """
    return len(decoded_token["access"]) == 0


def contains_accessible_actions(decoded_token, scope):
    """
    Check if a client has permission to perform operations within the current scope
    """
    for access in decoded_token["access"]:
        if scope.resource_type == access["type"] and scope.name == access["name"]:
            if scope.action in access["actions"]:
                return True

    return False
