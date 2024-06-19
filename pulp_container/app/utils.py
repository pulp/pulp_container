import base64
import hashlib
import fnmatch
import re
import subprocess
import gnupg
import json
import logging
import time

from asgiref.sync import sync_to_async
from jsonschema import Draft7Validator, validate, ValidationError
from django.core.files.storage import default_storage as storage
from django.db import IntegrityError
from functools import partial
from rest_framework.exceptions import Throttled

from pulpcore.plugin.models import Artifact, Task

from pulp_container.constants import (
    MANIFEST_MEDIA_TYPES,
    MEDIA_TYPE,
)
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
            return True
        elif task.state in ["waiting", "running"]:
            continue
        else:
            raise Exception(str(task.error))
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
            if config_media_type == MEDIA_TYPE.CONFIG_BLOB:
                return MEDIA_TYPE.MANIFEST_V2
            else:
                return MEDIA_TYPE.MANIFEST_OCI
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


def calculate_digest(manifest):
    """
    Calculate the requested digest of the ImageManifest, given in JSON.

    Args:
        manifest (str | bytes):  The raw JSON representation of the Manifest.

    Returns:
        str: The digest of the given ImageManifest

    """
    decoded_manifest = json.loads(manifest)
    if isinstance(manifest, str):
        manifest = manifest.encode("utf-8")

    if "signatures" in decoded_manifest:
        # This manifest contains signatures. Unfortunately, the Docker manifest digest
        # is calculated on the unsigned version of the Manifest so we need to remove the
        # signatures. To do this, we will look at the 'protected' key within the first
        # signature. This key indexes a (malformed) base64 encoded JSON dictionary that
        # tells us how many bytes of the manifest we need to keep before the signature
        # appears in the original JSON and what the original ending to the manifest was after
        # the signature block. We will strip out the bytes after this cutoff point, add back the
        # original ending, and then calculate the sha256 sum of the transformed JSON to get the
        # digest.
        protected = decoded_manifest["signatures"][0]["protected"]
        # Add back the missing padding to the protected block so that it is valid base64.
        protected = pad_unpadded_b64(protected)
        # Now let's decode the base64 and load it as a dictionary so we can get the length
        protected = base64.b64decode(protected)
        protected = json.loads(protected)
        # This is the length of the signed portion of the Manifest, except for a trailing
        # newline and closing curly brace.
        signed_length = protected["formatLength"]
        # The formatTail key indexes a base64 encoded string that represents the end of the
        # original Manifest before signatures. We will need to add this string back to the
        # trimmed Manifest to get the correct digest. We'll do this as a one liner since it is
        # a very similar process to what we've just done above to get the protected block
        # decoded.
        signed_tail = base64.b64decode(pad_unpadded_b64(protected["formatTail"]))
        # Now we can reconstruct the original Manifest that the digest should be based on.
        manifest = manifest[:signed_length] + signed_tail

    return "sha256:{digest}".format(digest=hashlib.sha256(manifest).hexdigest())


def pad_unpadded_b64(unpadded_b64):
    """
    Fix bad padding.

    Docker has not included the required padding at the end of the base64 encoded
    'protected' block, or in some encased base64 within it. This function adds the correct
    number of ='s signs to the unpadded base64 text so that it can be decoded with Python's
    base64 library.

    Args:
        unpadded_b64 (str): The unpadded base64 text.

    Returns:
        str: The same base64 text with the appropriate number of ='s symbols.

    """
    # The Pulp team has not observed any newlines or spaces within the base64 from Docker, but
    # Docker's own code does this same operation so it seemed prudent to include it here.
    # See lines 167 to 168 here:
    # https://github.com/docker/libtrust/blob/9cbd2a1374f46905c68a4eb3694a130610adc62a/util.go
    unpadded_b64 = unpadded_b64.replace("\n", "").replace(" ", "")
    # It is illegal base64 for the remainder to be 1 when the length of the block is
    # divided by 4.
    if len(unpadded_b64) % 4 == 1:
        raise ValueError("Invalid base64: {t}".format(t=unpadded_b64))
    # Add back the missing padding characters, based on the length of the encoded string
    paddings = {0: "", 2: "==", 3: "="}
    return unpadded_b64 + paddings[len(unpadded_b64) % 4]


async def save_artifact(artifact_attributes):
    saved_artifact = Artifact(**artifact_attributes)
    try:
        await saved_artifact.asave()
    except IntegrityError:
        del artifact_attributes["file"]
        saved_artifact = await Artifact.objects.aget(**artifact_attributes)
        await sync_to_async(saved_artifact.touch)()
    return saved_artifact


def get_content_data(saved_artifact):
    with storage.open(saved_artifact.file.name, mode="rb") as file:
        raw_data = file.read()
    content_data = json.loads(raw_data)
    return content_data, raw_data


def include(x, patterns):
    return any(fnmatch.fnmatch(x, pattern) for pattern in patterns)


def exclude(x, patterns):
    return not include(x, patterns)


def filter_resource(element, include_patterns, exclude_patterns):
    """
    Returns true if element matches {include,exclude}_patterns filters.
    """
    if not (include_patterns or exclude_patterns):
        return True
    return include(element, include_patterns or []) and exclude(element, exclude_patterns or [])


def filter_resources(element_list, include_patterns, exclude_patterns):
    """
    Returns a list of elements based on filter parameters ({include,exclude}_patterns).
    """
    if include_patterns:
        element_list = filter(partial(include, patterns=include_patterns), element_list)
    if exclude_patterns:
        element_list = filter(partial(exclude, patterns=exclude_patterns), element_list)
    return list(element_list)
