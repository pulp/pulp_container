import re
import jwt

from aiohttp import web
from django.conf import settings

CONTENT_HOST = re.sub(r'(http://|https://)', '', settings.CONTENT_ORIGIN, count=1)


class TokenVerifier:
    """A class used for a token verification."""

    def __init__(self, request, access_action):
        """
        Store data required for the token verification.

        Args:
            request (:class:`~aiohttp.web.Request`): The request with an Authorization header.
            access_action (str): A required action to perform pulling/pushing.

        """
        self.request = request
        self.access_action = access_action

    def verify(self):
        """Verify a Bearer token."""
        authorization = self.get_authorization_header()
        self.check_authorization_token(authorization)

    def get_authorization_header(self):
        """
        Fetch an Authorization header from the request.

        Raises:
            web.HTTPUnauthorized: An Authorization header is missing in the header.

        Returns:
            A raw string containing a Bearer token.

        """
        try:
            return self.request.headers['Authorization']
        except KeyError:
            raise web.HTTPUnauthorized(
                headers=self._build_response_headers(),
                reason='Access to the requested resource is not authorized. '
                       'A Bearer token is missing in a request header.'
            )

    def check_authorization_token(self, authorization):
        """
        Check if a Bearer token is valid.

        Args:
            authorization: A string containing a Bearer token.

        Raises:
            web.HTTPUnauthorized: A Bearer token is not valid.

        """
        token = self._get_token(authorization)
        if not self.is_token_valid(token):
            raise web.HTTPUnauthorized(
                headers=self._build_response_headers(),
                reason='Access to the requested resource is not authorized. '
                       'A provided Bearer token is invalid.'
            )

    def _get_token(self, authorization):
        """
        Get a raw token string from the header.

        This method returns a string that skips the keyword 'Bearer' and an additional
        space from the header (e.g. "Bearer abcdef123456" -> "abcdef123456").
        """
        return authorization[7:]

    def _build_response_headers(self):
        """
        Build headers that a registry returns as a response to unauthorized access.

        The method creates a value for the Www-Authenticate header. This value is used
        by a client for requesting a Bearer token from a token server. The header
        Docker-Distribution-API-Version is generated too to inform the client about
        the supported schema type.
        """
        source_path = self._get_current_content_path()
        authenticate_header = self._build_authenticate_string(source_path)

        headers = {
            'Docker-Distribution-API-Version': 'registry/2.0',
            'Www-Authenticate': authenticate_header
        }
        return headers

    def _build_authenticate_string(self, source_path):
        """
        Build a formatted authenticate string.

        For example, a created string will be the in following format:
        realm="http://localhost:123/token",service="docker.io",scope="repository:app:push".
        """
        realm = settings.TOKEN_SERVER
        authenticate_string = f'Bearer realm="{realm}",service="{CONTENT_HOST}"'

        if not self._is_verifying_root_endpoint():
            scope = f'repository:{source_path}:pull'
            authenticate_string += f',scope="{scope}"'

        return authenticate_string

    def is_token_valid(self, encoded_token):
        """Decode and validate a token."""
        with open(settings.PUBLIC_KEY_PATH, 'rb') as public_key:
            decoded_token = self.decode_token(encoded_token, public_key.read())

        return self.contains_accessible_actions(decoded_token)

    def decode_token(self, encoded_token, public_key):
        """
        Decode token and verify a signature with a public key.

        If the token could not be decoded with a success, a client does not have a
        permission to operate with a registry.
        """
        jwt_config = self._init_jwt_decoder_config()
        try:
            decoded_token = jwt.decode(encoded_token, public_key, **jwt_config)
        except jwt.exceptions.InvalidTokenError:
            decoded_token = {'access': []}
        return decoded_token

    def _init_jwt_decoder_config(self):
        """Initialize a basic configuration used for sanitizing and decoding a token."""
        return {
            'algorithms': [settings.TOKEN_SIGNATURE_ALGORITHM],
            'issuer': settings.TOKEN_SERVER,
            'audience': CONTENT_HOST
        }

    def contains_accessible_actions(self, decoded_token):
        """Check if a client has an access permission to execute the pull/push operation."""
        for access in decoded_token['access']:
            if self._targets_current_content_path(access):
                return True

        return False

    def _targets_current_content_path(self, access):
        """
        Check if a client targets a valid content path.

        When a client targets the root endpoint, the verifier does not necessary need to
        check for the pull or push access permission, therefore, it is granted automatically.
        """
        content_path = self._get_current_content_path()

        if content_path == access['name']:
            if self.access_action in access['actions']:
                return True
            if self._is_verifying_root_endpoint():
                return True

        return False

    def _get_current_content_path(self):
        """
        Retrieve a content path from the request.

        If the path does not exist, it means that a client is querying a root endpoint.
        """
        try:
            content_path = self.request.match_info['path']
        except KeyError:
            content_path = ''
        return content_path

    def _is_verifying_root_endpoint(self):
        """If the root endpoint is queried, no matching info is present."""
        return not bool(self.request.match_info)

    @classmethod
    def verify_from(cls, request, access_action):
        """Verify Bearer token and initialize the verifier from the request and the access."""
        token_verifier = cls(request, access_action)
        token_verifier.verify()
