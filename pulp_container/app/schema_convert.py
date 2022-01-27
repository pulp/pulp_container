import base64
import binascii
import datetime
import ecdsa
import hashlib
import itertools
import json
import logging

from gettext import gettext as _

from collections import namedtuple
from jwkest import jws, jwk, ecc

from django.core.exceptions import ObjectDoesNotExist

from pulp_container.constants import MEDIA_TYPE

log = logging.getLogger(__name__)

FS_Layer = namedtuple("FS_Layer", "layer_id uncompressed_digest history")
ConversionResult = namedtuple("ConversionResult", "text digest content_type")


class Schema2toSchema1ConverterWrapper:
    """An abstraction around creating new manifests of the format schema 1."""

    def __init__(self, tag, accepted_media_types, path):
        """Store a tag object, accepted media type, and path."""
        self.path = path
        self.tag = tag
        self.accepted_media_types = accepted_media_types
        self.name = path

    def convert(self):
        """Convert a manifest to schema 1.

        Raises:
            RuntimeError: If the conversion was not successful.

        Returns:
            ConversionResult: A converted manifest, corresponding digest, and content type.

        """
        if self.tag.tagged_manifest.media_type == MEDIA_TYPE.MANIFEST_V2:
            schema_with_signature, digest = self._convert_schema(self.tag.tagged_manifest)
            return ConversionResult(schema_with_signature, digest, MEDIA_TYPE.MANIFEST_V1_SIGNED)
        elif self.tag.tagged_manifest.media_type == MEDIA_TYPE.MANIFEST_LIST:
            legacy = self._get_legacy_manifest()
            if legacy.media_type in self.accepted_media_types:
                # return legacy without conversion
                legacy_schema = _jsonDumps(_get_manifest_dict(legacy))
                return ConversionResult(legacy_schema, legacy.digest, legacy.media_type)
            elif legacy.media_type == MEDIA_TYPE.MANIFEST_V2:
                schema_with_signature, digest = self._convert_schema(legacy)
                return ConversionResult(
                    schema_with_signature, digest, MEDIA_TYPE.MANIFEST_V1_SIGNED
                )
            else:
                raise RuntimeError()

    def _convert_schema(self, manifest):
        config_dict = _get_config_dict(manifest)
        manifest_dict = _get_manifest_dict(manifest)

        try:
            converter = Schema2toSchema1Converter(
                manifest_dict, config_dict, name=self.name, tag=self.tag.name
            )
        except ValueError:
            raise RuntimeError()

        converted_schema, schema_with_signature = converter.convert()

        # According to the docs https://docs.docker.com/registry/spec/api/#content-digests,
        # the digest header is deduced from the manifest body without the signature content.
        # Therefore, the digest is computed from the formatted and converted manifest here.
        digest = compute_digest(converted_schema)
        return schema_with_signature, digest

    def _get_legacy_manifest(self):
        ml = self.tag.tagged_manifest.listed_manifests.all()
        for manifest in ml:
            m = manifest.manifest_lists.first()
            if m.architecture == "amd64" and m.os == "linux":
                return m.manifest_list

        raise RuntimeError()


class Schema2toSchema1Converter:
    """
    Converter class from schema 2 to schema 1.

    Initialize it with a manifest and a config layer JSON documents,
    and call convert() to obtain the signed manifest, as a JSON-encoded string.
    """

    EMPTY_LAYER = "sha256:a3ed95caeb02ffe68cdd9fd84406680ae93d633cb16422d00e8a7c22955b46d4"

    def __init__(self, manifest, config_layer, name, tag):
        """
        Initializer needs a manifest and a config layer as JSON documents.
        """
        self.name = name
        self.tag = tag
        self.manifest = manifest
        self.config_layer = config_layer
        self.fs_layers = []
        self.history = []

        self._assert_foreign_layers()

    def _assert_foreign_layers(self):
        for layer in self.manifest["layers"]:
            if layer.get("mediaType") == MEDIA_TYPE.FOREIGN_BLOB:
                raise ValueError("The conversion cannot be applied for foreign layers.")

    def convert(self):
        """
        Convert manifest from schema 2 to schema 1
        """
        self.compute_layers()
        manifest = dict(
            name=self.name,
            tag=self.tag,
            architecture=self.config_layer["architecture"],
            schemaVersion=1,
            fsLayers=self.fs_layers,
            history=self.history,
        )

        key = jwk.ECKey().load_key(ecc.P256)
        key.kid = getKeyId(key)
        manifest_data = _jsonDumps(manifest)
        signed_manifest_data = sign(manifest_data, key)
        return manifest_data, signed_manifest_data

    def compute_layers(self):
        """
        Compute layers to be present in the converted image.
        Empty (throwaway) layers will be created to store image metadata
        """
        # Layers in v2s1 are in reverse order from v2s2
        fs_layers = self._compute_fs_layers()
        self.fs_layers = [dict(blobSum=x[0]) for x in fs_layers]
        # Compute v1 compatibility
        parent = None
        history_entries = self.history = []

        fs_layers_count = len(fs_layers)
        # Reverse list so we can compute parent/child properly
        fs_layers.reverse()
        for i, fs_layer in enumerate(fs_layers):
            layer_id = self._compute_layer_id(fs_layer.layer_id, fs_layer.uncompressed_digest, i)
            config = self._compute_v1_compatibility_config(
                layer_id, fs_layer, last_layer=(i == fs_layers_count - 1)
            )
            if parent is not None:
                config["parent"] = parent
            parent = layer_id
            history_entries.append(dict(v1Compatibility=_jsonDumpsCompact(config)))
        # Reverse again for proper order
        history_entries.reverse()

    def _compute_fs_layers(self):
        """Utility function to return a list of FS_Layer objects"""
        layers = reversed(self.manifest["layers"])
        config_layer_history = reversed(self.config_layer["history"])
        diff_ids = reversed(self.config_layer["rootfs"]["diff_ids"])
        fs_layers = []
        curr_compressed_dig = next(layers)["digest"]
        curr_uncompressed_dig = next(diff_ids)
        for curr_hist in config_layer_history:
            if curr_hist.get("empty_layer"):
                layer_id = self.EMPTY_LAYER
                uncompressed_dig = None
            else:
                layer_id = curr_compressed_dig
                uncompressed_dig = curr_uncompressed_dig
                try:
                    curr_compressed_dig = next(layers)["digest"]
                    curr_uncompressed_dig = next(diff_ids)
                except StopIteration:
                    curr_compressed_dig = self.EMPTY_LAYER
                    curr_uncompressed_dig = None
            fs_layers.append(FS_Layer(layer_id, uncompressed_dig, curr_hist))
        return fs_layers

    def _compute_v1_compatibility_config(self, layer_id, fs_layer, last_layer=False):
        """Utility function to compute the v1 compatibility"""
        if last_layer:
            # The whole config layer becomes part of the v1compatibility
            # (minus history and rootfs)
            config = dict(self.config_layer)
            config.pop("history", None)
            config.pop("rootfs", None)
        else:
            # both `created` and `created_by` are optional according to the OCI specs
            container_config = dict(Cmd=[fs_layer.history.get("created_by", "")])
            created = fs_layer.history.get("created", "")
            config = dict(
                created=created,
                container_config=container_config,
            )
        if fs_layer.uncompressed_digest is None:
            config["throwaway"] = True
        config["id"] = layer_id
        return config

    @classmethod
    def _compute_layer_id(cls, compressed_dig, uncompressed_dig, layer_index):
        """
        We need to make up an image ID for each layer.
        We will digest:
        * the compressed digest of the layer
        * the uncompressed digest (if present; it will be missing for throw-away layers)
        * the zero-padded integer of the layer number
        The last one is added so we can get different image IDs for throw-away layers.
        """
        dig = hashlib.sha256(compressed_dig.encode("ascii"))
        if uncompressed_dig:
            dig.update(uncompressed_dig.encode("ascii"))
        layer_count = "%06d" % layer_index
        dig.update(layer_count.encode("ascii"))
        layer_id = dig.hexdigest()
        return layer_id


def _jsonDumps(data):
    return json.dumps(data, indent=3, sort_keys=True, separators=(",", ": "))


def _jsonDumpsCompact(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def sign(data, key):
    """
    Sign the JSON data with the passed key.
    """
    now = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    header = dict(alg="ES256", jwk=key.serialize())
    protected = dict(formatLength=len(data) - 2, formatTail=jws.b64encode_item(data[-2:]), time=now)
    _jws = jws.JWS(data, **header)
    protectedHeader, payload, signature = _jws.sign_compact([key], protected=protected).split(".")
    signatures = [dict(header=header, signature=signature, protected=protectedHeader)]
    jsig = _jsonDumps(dict(signatures=signatures))[1:-2]
    arr = [data[:-2], ",", jsig, data[-2:]]
    # Add the signature block at the end of the json string, keeping the formatting
    data_with_signature = "".join(arr)
    return data_with_signature


def getKeyId(key):
    """
    DER-encode the key and represent it in the format XXXX:YYYY:...
    """
    derRepr = toDer(key)
    shaRepr = hashlib.sha256(derRepr).digest()[:30]
    b32Repr = base64.b32encode(shaRepr).decode()
    return ":".join(byN(b32Repr, 4))


def toDer(key):
    """Return the DER-encoded representation of the key"""
    point = (
        b"\x00\x04" + number2string(key.x, key.curve.bytes) + number2string(key.y, key.curve.bytes)
    )
    der = ecdsa.der
    curveEncodedOid = der.encode_oid(1, 2, 840, 10045, 3, 1, 7)
    return der.encode_sequence(
        der.encode_sequence(ecdsa.keys.encoded_oid_ecPublicKey, curveEncodedOid),
        der.encode_bitstring(point),
    )


def byN(strobj, N):
    """
    Yield consecutive substrings of length N from string strobj
    """
    it = iter(strobj)
    while True:
        substr = "".join(itertools.islice(it, N))
        if not substr:
            return
        yield substr


def number2string(num, order):
    """
    Hex-encode the number and return a zero-padded (to the left) to a total
    length of 2*order
    """
    # convert to hex
    nhex = "%x" % num
    # Zero-pad to the left so the length of the resulting unhexified string is order
    nhex = nhex.rjust(2 * order, "0")
    return binascii.unhexlify(nhex)


def compute_digest(manifest_data):
    """
    Compute the digest from the passed manifest data.
    """

    hexdigest = hashlib.sha256(manifest_data.encode("utf-8")).hexdigest()
    digest = "sha256:{}".format(hexdigest)
    return digest


def _get_config_dict(manifest):
    try:
        config_artifact = manifest.config_blob._artifacts.get()
    except ObjectDoesNotExist:
        raise RuntimeError()
    return _get_dict(config_artifact)


def _get_manifest_dict(manifest):
    try:
        manifest_artifact = manifest._artifacts.get()
    except ObjectDoesNotExist:
        raise RuntimeError()
    return _get_dict(manifest_artifact)


def _get_dict(artifact):
    try:
        return json.load(artifact.file)
    except FileNotFoundError:
        raise Exception(
            _(
                "Expected manifest file 'sha256:{}' needed for schema conversion is not found"
            ).format(artifact.sha256)
        )
