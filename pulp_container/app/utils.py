import re
import subprocess
import gnupg
import json
import logging
import time

from jsonschema import Draft7Validator, validate, ValidationError
from rest_framework.exceptions import Throttled

from pulpcore.plugin.models import Task

from pulp_container.constants import MANIFEST_MEDIA_TYPES, MEDIA_TYPE
from pulp_container.app.exceptions import ManifestInvalid
from pulp_container.app.json_schemas import (
    OCI_INDEX_SCHEMA,
    OCI_MANIFEST_SCHEMA,
    DOCKER_MANIFEST_LIST_V2_SCHEMA,
    DOCKER_MANIFEST_V2_SCHEMA,
    DOCKER_MANIFEST_V1_SCHEMA,
    SIGNATURE_SCHEMA,
)

KEY_ID_REGEX_COMPILED = re.compile(r"keyid ([0-9A-F]+)")
TIMESTAMP_REGEX_COMPILED = re.compile(r"created ([0-9]+)")

signature_validator = Draft7Validator(SIGNATURE_SCHEMA)

log = logging.getLogger(__name__)


def get_accepted_media_types(headers):
    """
    Returns a list of media types from the Accept headers.

    Args:
        headers (:class:`~aiohttp.multidict.CIMultiDictProxy` or dict):
            The request's headers to extract accepted media types from.

    Returns:
        List of media types supported by the client.

    """
    accepted_media_types = []
    for header, values in headers.items():
        if header == "Accept":
            values = [v.strip() for v in values.split(",")]
            accepted_media_types.extend(values)
    return accepted_media_types


def urlpath_sanitize(*args):
    """
    Join an arbitrary number of strings into a /-separated path.
    Replaces uses of urljoin() that don't want/need urljoin's subtle semantics.
    Returns: single string provided arguments separated by single-slashes
    Args:
        Arbitrary list of arguments to be join()ed

    [stolen from pulp_rpm]
    """

    segments = []
    for a in args + ("",):
        stripped = a.strip("/")
        if stripped:
            segments.append(stripped)
    return "/".join(segments)


def extract_data_from_signature(signature_raw, man_digest):
    """
    Extract data from an "integrated" signature, aka a signed non-encrypted document.

    Args:
        signature_raw(bytes): A signed doc to get data from
        man_digest (str): A manifest digest for which the signature is for

    Returns:
        dict: JSON representation of the document and available data about signature

    """
    gpg = gnupg.GPG()
    crypt_obj = gpg.decrypt(signature_raw, extra_args=["--skip-verify"])
    if not crypt_obj.data:
        log.info(
            "It is not possible to read the signed document, GPG error: {}".format(crypt_obj.stderr)
        )
        return

    try:
        sig_json = json.loads(crypt_obj.data)
    except Exception as exc:
        log.info(
            "Signed document cannot be parsed to create a signature for {}."
            " Error: {}".format(man_digest, str(exc))
        )
        return

    errors = []
    for error in signature_validator.iter_errors(sig_json):
        errors.append(f'{".".join(error.path)}: {error.message}')

    if errors:
        log.info("The signature for {} is not synced due to: {}".format(man_digest, errors))
        return

    # decrypted and unverified signatures do not have prepopulated the key_id and timestamp
    # fields; thus, it is necessary to use the debugging utilities of gpg to extract these
    # fields since they are not encrypted and still readable without decrypting the signature first
    packets = subprocess.check_output(["gpg", "--list-packets"], input=signature_raw).decode()
    sig_json["signing_key_id"] = KEY_ID_REGEX_COMPILED.search(packets).group(1)
    sig_json["signature_timestamp"] = TIMESTAMP_REGEX_COMPILED.search(packets).group(1)

    return sig_json


def has_task_completed(dispatched_task, wait_in_seconds=3):
    """
    Wait a couple of seconds until the task finishes its run.

    Returns:
        bool: True if the task ends successfully.

    Raises:
        Exception: If an error occurs during the task's runtime.
        Throttled: If the task did not finish within a predefined timespan.

    """
    for dummy in range(wait_in_seconds):
        time.sleep(1)
        task = Task.objects.get(pk=dispatched_task.pk)
        if task.state == "completed":
            task.delete()
            return True
        elif task.state in ["waiting", "running"]:
            continue
        else:
            error = task.error
            task.delete()
            raise Exception(str(error))
    raise Throttled()


def determine_media_type(content_data, response):
    """Determine the media type of a manifest either from the JSON data or the response object."""
    if media_type := content_data.get("mediaType"):
        return media_type
    elif media_type := response.headers.get("content-type"):
        # translate v1 signed media_type
        if media_type == MEDIA_TYPE.MANIFEST_V1_SIGNED:
            return MEDIA_TYPE.MANIFEST_V1
        elif media_type in MANIFEST_MEDIA_TYPES.IMAGE or media_type in MANIFEST_MEDIA_TYPES.LIST:
            return media_type
        else:
            pass
    return determine_media_type_from_json(content_data)


def determine_media_type_from_json(content_data):
    """Determine the media tpye of a manifest from the provided JSON data."""
    if media_type := content_data.get("mediaType"):
        return media_type
    elif manifests := content_data.get("manifests"):
        if len(manifests):
            # check if there is at least one oci manifest
            if set([m["mediaType"] for m in manifests]).intersection(
                (MEDIA_TYPE.MANIFEST_OCI, MEDIA_TYPE.INDEX_OCI)
            ):
                return MEDIA_TYPE.INDEX_OCI
        return MEDIA_TYPE.MANIFEST_LIST
    else:
        if config := content_data.get("config"):
            config_media_type = config.get("mediaType")
            if config_media_type == MEDIA_TYPE.CONFIG_BLOB_OCI:
                return MEDIA_TYPE.MANIFEST_OCI
            else:
                return MEDIA_TYPE.MANIFEST_V2
        else:
            return MEDIA_TYPE.MANIFEST_V1


def determine_schema(media_type):
    """Return a JSON schema based on the specified content type."""
    if media_type == MEDIA_TYPE.MANIFEST_V2:
        return DOCKER_MANIFEST_V2_SCHEMA
    elif media_type == MEDIA_TYPE.MANIFEST_OCI:
        return OCI_MANIFEST_SCHEMA
    elif media_type == MEDIA_TYPE.MANIFEST_LIST:
        return DOCKER_MANIFEST_LIST_V2_SCHEMA
    elif media_type == MEDIA_TYPE.INDEX_OCI:
        return OCI_INDEX_SCHEMA
    elif media_type in (MEDIA_TYPE.MANIFEST_V1, MEDIA_TYPE.MANIFEST_V1_SIGNED):
        return DOCKER_MANIFEST_V1_SCHEMA
    else:
        raise ValueError()


def validate_manifest(content_data, media_type, digest):
    """Validate JSON data (manifest) according to its declared content type (e.g., list)."""
    try:
        schema_validator = determine_schema(media_type)
    except ValueError:
        raise ManifestInvalid(
            reason=f"A manifest of an unknown media type was provided: {media_type}",
            digest=digest,
        )

    try:
        validate(content_data, schema_validator)
    except ValidationError as error:
        # fail on the first encountered error
        raise ManifestInvalid(
            reason=f'{".".join(map(str, error.path))}: {error.message}', digest=digest
        )
