import base64
import hashlib
import random
import uuid

import jwt

from collections import defaultdict, namedtuple
from datetime import datetime

from django.conf import settings
from django.http import HttpRequest
from rest_framework.request import Request

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

from pulp_container.app.models import ContainerDistribution, ContainerNamespace
from pulp_container.app.access_policy import RegistryAccessPolicy

TOKEN_EXPIRATION_TIME = settings.get("TOKEN_EXPIRATION_TIME", 300)

FakeView = namedtuple("FakeView", ["action", "get_object"])


class AuthorizationService:
    """
    A class responsible for generating and managing a Bearer token.

    This class represents a token server which manages and grants permissions
    according to a user's scope.
    """

    def __init__(self, user, service, scope):
        """
        Store class-wide variables and initialize a dictionary used for determining permissions.

        Args:
            user (django.contrib.auth.models.User): Requesting user.
            service (str): Name of the service access is granted to.
            scope (str): Scope of the resource that is to be accessed.

        """
        self.user = user
        self.service = service
        self.scope = scope
        self.access_policy = RegistryAccessPolicy()

        self.actions_permissions = defaultdict(
            lambda: lambda *args: False,
            {
                "pull": self.has_pull_permissions,
                "push": self.has_push_permissions,
                "*": self.has_view_catalog_permissions,
            },
        )

    def generate_token(self):
        """
        Generate a Bearer token.

        A signed JSON web token is generated in this method. The structure of the token is
        adjusted according the documentation https://docs.docker.com/registry/spec/auth/jwt/.

        Returns:
            dict: A newly generated Bearer token.

        """
        with open(settings.PUBLIC_KEY_PATH, "rb") as public_key:
            kid = self.generate_kid_header(public_key.read())

        current_datetime = datetime.now()

        access = self.determine_access()
        token_server = getattr(settings, "TOKEN_SERVER", "")
        claim_set = self.generate_claim_set(
            access=access,
            audience=self.service,
            issued_at=int(current_datetime.timestamp()),
            issuer=token_server,
            subject=self.user.username,
        )

        with open(settings.PRIVATE_KEY_PATH, "rb") as private_key:
            binary_token = jwt.encode(
                claim_set,
                private_key.read(),
                algorithm=settings.TOKEN_SIGNATURE_ALGORITHM,
                headers={"kid": kid},
            )
        token = binary_token.decode("utf8")
        current_datetime_utc = current_datetime.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        return {
            "expires_in": TOKEN_EXPIRATION_TIME,
            "issued_at": current_datetime_utc,
            "token": token,
        }

    def generate_kid_header(self, public_key):
        """Generate kid header in a libtrust compatible format."""
        decoded_key = self._convert_key_format_from_pem_to_der(public_key)
        truncated_sha256 = hashlib.sha256(decoded_key).hexdigest()[:30].encode("utf8")
        encoded_base32 = base64.b32encode(truncated_sha256).decode("utf8")
        return self._split_into_encoded_groups(encoded_base32)

    def _convert_key_format_from_pem_to_der(self, public_key):
        key_in_pem_format = serialization.load_pem_public_key(public_key, default_backend())
        key_in_der_format = key_in_pem_format.public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return key_in_der_format

    def _split_into_encoded_groups(self, encoded_base32):
        """Split encoded and truncated base32 into 12 groups separated by ':'."""
        kid = encoded_base32[:4]
        for index, char in enumerate(encoded_base32[4:], start=0):
            if index % 4 == 0:
                kid += ":" + char
            else:
                kid += char
        return kid

    def determine_access(self):
        """
        Determine access permissions for a corresponding user.

        This method determines whether the user has a valid access permission or not.
        The determination is based on role based access control.

        Returns:
            list: An intersected set of the requested and the allowed access if the scope was
                specified. Otherwise, returns an empty list indicating permission for the root
                endpoint.

        """
        if not self.scope:
            return []

        typ, name, actions = self.scope.split(":")
        actions = set(actions.split(","))

        permitted_actions = set()
        if "push" in actions:
            actions.remove("push")
            has_permission = self.actions_permissions["push"](name)
            if has_permission:
                permitted_actions.add("push")
                permitted_actions.add("pull")
                actions.discard("pull")

        for action in actions:
            has_permission = self.actions_permissions[action](name)
            if has_permission:
                permitted_actions.add(action)

        return [{"type": typ, "name": name, "actions": list(permitted_actions)}]

    def has_permission(self, obj, method, action, data):
        """Check if user has permission to perform action."""

        # Fake the request
        request = Request(HttpRequest())
        request.method = method
        request.user = self.user
        request._full_data = data
        # Fake the corresponding view
        view = FakeView(action, lambda: obj)
        return self.access_policy.has_permission(request, view)

    def has_pull_permissions(self, path):
        """
        Check if the user has permissions to pull from the repository specified by the path.
        """
        try:
            distribution = ContainerDistribution.objects.get(base_path=path)
        except ContainerDistribution.DoesNotExist:
            namespace_name = path.split("/")[0]
            try:
                namespace = ContainerNamespace.objects.get(name=namespace_name)
            except ContainerNamespace.DoesNotExist:
                # Check if user is allowed to create a new namespace
                return self.has_permission(None, "POST", "create", {"name": namespace_name})
            # Check if user is allowed to view distributions in the namespace
            return self.has_permission(
                namespace, "GET", "view_distribution", {"name": namespace_name}
            )

        return self.has_permission(distribution, "GET", "pull", {"base_path": path})

    def has_push_permissions(self, path):
        """
        Check if the user has permissions to push to the repository specified by the path.
        """
        try:
            distribution = ContainerDistribution.objects.get(base_path=path)
        except ContainerDistribution.DoesNotExist:
            namespace_name = path.split("/")[0]
            try:
                namespace = ContainerNamespace.objects.get(name=namespace_name)
            except ContainerNamespace.DoesNotExist:
                # Check if user is allowed to create a new namespace
                return self.has_permission(None, "POST", "create", {"name": namespace_name})
            # Check if user is allowed to create a new distribution in the namespace
            return self.has_permission(namespace, "POST", "create_distribution", {})

        return self.has_permission(distribution, "POST", "push", {"base_path": path})

    def has_view_catalog_permissions(self, path):
        """
        Check if the authenticated user has permission to access the catalog endpoint.
        """
        if path != "catalog":
            return False

        # Fake the request
        request = Request(HttpRequest())
        request.method = "GET"
        request.user = self.user
        # Fake the view
        view = FakeView("catalog", lambda: ContainerDistribution())
        return self.access_policy.has_permission(request, view)

    @staticmethod
    def generate_claim_set(issuer, issued_at, subject, audience, access):
        """
        Generate the claim set that will be signed and dispatched back to the requesting subject.
        """
        token_id = str(uuid.UUID(int=random.getrandbits(128), version=4))
        expiration = issued_at + TOKEN_EXPIRATION_TIME
        return {
            "access": access,
            "aud": audience,
            "exp": expiration,
            "iat": issued_at,
            "iss": issuer,
            "jti": token_id,
            "nbf": issued_at,
            "sub": subject,
        }
