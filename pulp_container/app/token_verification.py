import jwt
import logging

from collections import namedtuple

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model

from rest_framework.authentication import BaseAuthentication, BasicAuthentication
from rest_framework.exceptions import AuthenticationFailed, NotAuthenticated
from rest_framework.permissions import BasePermission, SAFE_METHODS

Scope = namedtuple("Scope", "resource_type, name, action")
User = get_user_model()


log = logging.getLogger(__name__)


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


def _contains_accessible_actions(decoded_token, scope):
    """
    Check if a client has permission to perform operations within the current scope
    """
    for access in decoded_token["access"]:
        if scope.resource_type == access["type"] and scope.name == access["name"]:
            if scope.action in access["actions"]:
                return True

    return False


class RegistryAuthentication(BasicAuthentication):
    """
    A basic authentication class that accepts empty username and password as anonymous.
    """

    def authenticate(self, request):
        """
        Perform basic authentication with the exception to accept empty credentials.
        For anonymous user, Podman sends 'Authorization': 'Basic Og=='.
        This represents ":" in base64.
        """
        if request.headers.get("Authorization") == "Basic Og==":
            return (AnonymousUser, None)

        return super().authenticate(request)


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
                code="invalid_token",
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

        scope = get_scope(request)
        if scope is not None:
            authenticate_string += f',scope="{scope.resource_type}:{scope.name}:{scope.action}"'

        return authenticate_string


def get_scope(request):
    """
    Return an initialized scope object based on the passed request's data.
    """
    path = request.resolver_match.kwargs.get("path", "")
    if path:
        action = "pull" if request.method in SAFE_METHODS else "push"
        return Scope("repository", path, action)
    elif request.path == "/v2/_catalog":
        return Scope("registry", "catalog", "*")
    elif request.path == "/v2/":
        return None


class RegistryPermission(BasePermission):
    """
    Permission class to determine permissions based on the request user.
    """

    message = "Access to the requested resource is not authorized."

    def has_permission(self, request, view):
        """
        Decide upon permission based on user.
        """
        if request.user.is_staff:
            return True
        if request.method in SAFE_METHODS:
            return True

        return False


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
        if decoded_token is None:
            raise NotAuthenticated()

        scope = get_scope(request)
        if scope is None:
            is_requesting_root_endpoint = len(decoded_token["access"]) == 0
            if is_requesting_root_endpoint:
                return True
        else:
            if _contains_accessible_actions(decoded_token, scope):
                return True

        raise AuthenticationFailed(detail="Insufficient permissions", code="insufficient_scope")
