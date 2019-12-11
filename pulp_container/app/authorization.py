import re
import base64
import hashlib
import random
import uuid

import jwt

from datetime import datetime
from aiohttp import web

from django.conf import settings
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

from pulpcore.plugin.content import Handler

TOKEN_EXPIRATION_TIME = 300

KNOWN_SERVICES = [re.sub(r'(http://|https://)', '', settings.CONTENT_ORIGIN, count=1)]
ANONYMOUS_USER = ''
EMPTY_ACCESS_SCOPE = '::'


class AuthorizationService(Handler):
    """
    A class responsible for generating and managing a Bearer token.

    This class represents a token server which manages and grants permissions
    according to a user's scope.
    """

    async def generate_token(self, request):
        """
        Generate a Bearer token.

        A signed JSON web token is generated in this method. The structure of the token is
        adjusted according the documentation https://docs.docker.com/registry/spec/auth/jwt/.

        Args:
            request(:class:`~aiohttp.web.Request`): The request to prepare a response for.

        Returns:
            class:`aiohttp.web_response.Response`: A newly generated Bearer token.

        """
        with open(settings.PUBLIC_KEY_PATH, 'rb') as public_key:
            kid = self.generate_kid_header(public_key.read())

        current_datetime = datetime.now()

        token_queries = TokenRequestQueries.init_from(request)
        access = self.determine_access(ANONYMOUS_USER, token_queries.scope)
        token_server = getattr(settings, 'TOKEN_SERVER', '')
        claim_set = self._generate_claim_set(
            access=[access],
            audience=token_queries.service,
            issued_at=int(current_datetime.timestamp()),
            issuer=token_server,
            subject=ANONYMOUS_USER
        )

        with open(settings.PRIVATE_KEY_PATH, 'rb') as private_key:
            binary_token = jwt.encode(
                claim_set, private_key.read(),
                algorithm=settings.TOKEN_SIGNATURE_ALGORITHM,
                headers={'kid': kid}
            )
        token = binary_token.decode('utf8')
        current_datetime_utc = current_datetime.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        return web.json_response({
            'expires_in': TOKEN_EXPIRATION_TIME,
            'issued_at': current_datetime_utc,
            'token': token
        })

    def generate_kid_header(self, public_key):
        """Generate kid header in a libtrust compatible format."""
        decoded_key = self._convert_key_format_from_pem_to_der(public_key)
        truncated_sha256 = hashlib.sha256(decoded_key).hexdigest()[:30].encode('utf8')
        encoded_base32 = base64.b32encode(truncated_sha256).decode('utf8')
        return self._split_into_encoded_groups(encoded_base32)

    def _convert_key_format_from_pem_to_der(self, public_key):
        key_in_pem_format = serialization.load_pem_public_key(public_key, default_backend())
        key_in_der_format = key_in_pem_format.public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return key_in_der_format

    def _split_into_encoded_groups(self, encoded_base32):
        """Split encoded and truncated base32 into 12 groups separated by ':'."""
        kid = encoded_base32[:4]
        for index, char in enumerate(encoded_base32[4:], start=0):
            if index % 4 == 0:
                kid += ':' + char
            else:
                kid += char
        return kid

    def determine_access(self, user, scope):
        """
        Determine access permissions for a corresponding user.

        This method determines whether the user has a valid access permission or not.
        The determination is based on role based access control. For now, the access
        is given out to anybody because the role based access control is not implemented
        yet.

        Args:
            user (str): A name of the user who is trying to access a registry.
            scope (str): A requested scope.

        Returns:
            list: An intersected set of the requested and the allowed access.

        """
        typ, name, actions = scope.split(':')
        actions_list = actions.split(',')
        permitted_actions = list(set(actions_list).intersection(['pull']))
        return {'type': typ, 'name': name, 'actions': permitted_actions}

    def _generate_claim_set(self, issuer, issued_at, subject, audience, access):
        token_id = str(uuid.UUID(int=random.getrandbits(128), version=4))
        expiration = issued_at + TOKEN_EXPIRATION_TIME
        return {
            'access': access,
            'aud': audience,
            'exp': expiration,
            'iat': issued_at,
            'iss': issuer,
            'jti': token_id,
            'nbf': issued_at,
            'sub': subject
        }


class TokenRequestQueries:
    """A data class that holds data retrieved from the request queries."""

    def __init__(self, scope, service):
        """
        Store a scope and a service.

        Args:
            scope (str): A requested scope.
            service (str): A service that request a Bearer token.

        """
        self.scope = scope
        self.service = service

    @classmethod
    def init_from(cls, request):
        """
        Initialize the actual class with data retrieved from the request queries.

        In this method, a validity and a presence of required queries (scope, service)
        is checked as well. If the scope is not specified, the method checks if a user
        is trying to access root endpoint only. Then, the scope is not relevant anymore
        and initialized to empty type, name, and requested actions ('::').
        """
        try:
            scope = request.query['scope']
        except KeyError:
            if request.match_info:
                raise web.HTTPBadRequest(reason='A scope was not provided.')
            else:
                scope = EMPTY_ACCESS_SCOPE

        try:
            service = request.query['service']
        except KeyError:
            raise web.HTTPBadRequest(reason='A service name was not provided.')
        if service not in KNOWN_SERVICES:
            raise web.HTTPBadRequest(reason='A provided service is unknown.')

        return cls(scope, service)
