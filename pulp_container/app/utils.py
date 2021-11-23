from gettext import gettext as _

import gnupg
import json
import logging

from pulp_container.constants import SIGNATURE_TYPE


gpg = gnupg.GPG()
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
    crypt_obj = gpg.decrypt(signature_raw)
    if not crypt_obj.data:
        log.info(
            _(
                "It is not possible to read the signed document, GPG error: {}".format(
                    crypt_obj.stderr
                )
            )
        )
        return

    try:
        sig_json = json.loads(crypt_obj.data)
    except Exception as exc:
        log.info(
            _(
                "Signed document cannot be parsed to create a signature for {}."
                " Error: {}".format(man_digest, str(exc))
            )
        )
        return

    signature_type = sig_json["critical"].get("type") if "critical" in sig_json else None
    # Currently, the only supported type is ATOMIC.
    if signature_type != SIGNATURE_TYPE.ATOMIC_FULL:
        log.info(
            _(
                "Unsupported signature type {}, signature is not synced for {}.".format(
                    signature_type, man_digest
                )
            )
        )
        return

    sig_json["signing_key_id"] = crypt_obj.key_id
    sig_json["signature_timestamp"] = crypt_obj.timestamp
    return sig_json
