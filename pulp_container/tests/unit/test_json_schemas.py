import json

from jsonschema import Draft7Validator

from django.test import TestCase

from pulp_container.constants import MEDIA_TYPE
from pulp_container.app.exceptions import ManifestInvalid
from pulp_container.app.json_schemas import SIGNATURE_SCHEMA
from pulp_container.app.utils import validate_manifest

validator = Draft7Validator(SIGNATURE_SCHEMA)


class TestSignatureJsonSchema(TestCase):
    """A test case for validating the prescribed JSON schema for pushed signatures."""

    def test_valid_signature(self):
        """Check if a valid signature is successfully parsed."""
        signature = """{
            "critical": {
                "type": "atomic container signature",
                "image": {
                    "docker-manifest-digest": "sha256:123456"
                },
                "identity": {
                    "docker-reference": "docker.io/library/busybox:latest"
                }
            },
            "optional": {
                "creator": "some software package v1.0.1-35",
                "timestamp": 0
            }
        }"""
        signature = json.loads(signature)
        self.assertEqual(list(validator.iter_errors(signature)), [])

    def test_missing_optional_fields(self):
        """Test if the optional fields can be skipped in a signature payload."""
        signature = """{
            "critical": {
                "type": "atomic container signature",
                "image": {
                    "docker-manifest-digest": "sha256:123456"
                },
                "identity": {
                    "docker-reference": "docker.io/library/busybox:latest"
                }
            },
            "optional": {}
        }"""
        signature = json.loads(signature)
        self.assertEqual(list(validator.iter_errors(signature)), [])

    def test_missing_optional(self):
        """Test if the missing optional field is correctly addressed."""
        signature = """{
            "critical": {
                "type": "atomic container signature",
                "image": {
                    "docker-manifest-digest": "sha256:123456"
                },
                "identity": {
                    "docker-reference": "docker.io/library/busybox:latest"
                }
            }
        }"""
        signature = json.loads(signature)
        errors = list(ve.message for ve in validator.iter_errors(signature))
        if not any("optional" in error for error in errors):
            self.fail("The missing field 'optional' was not identified")

    def test_signature_missing_critical(self):
        """Test if the missing critical field is considered as an invalid JSON payload."""
        signature = """{
            "optional": {
                "creator": "some software package v1.0.1-35",
                "timestamp": 0
            }
        }"""
        signature = json.loads(signature)
        self.assertNotEqual(list(validator.iter_errors(signature)), [])

    def test_signature_missing_type_image_id(self):
        """Test if the missing required fields will raise a validator error."""
        signature = """{
            "critical": {},
            "optional": {
                "creator": "some software package v1.0.1-35",
                "timestamp": 0
            }
        }"""
        signature = json.loads(signature)
        errors = list(ve.message for ve in validator.iter_errors(signature))
        if not any("type" in error for error in errors):
            self.fail("The missing field 'type' was not identified")
        if not any("image" in error for error in errors):
            self.fail("The missing field 'image' was not identified")
        if not any("identity" in error for error in errors):
            self.fail("The missing field 'identity' was not identified")

    def test_signature_invalid_values(self):
        """Test if invalid values are properly identified."""
        signature = """{
            "critical": {
                "type": "atomic container signatureeeeeeeeeeeeeeeeeeeeeee",
                "image": {
                    "docker-manifest-digest": "sha256:123456"
                },
                "identity": {
                    "docker-reference": "docker.io/library/busybox:latest"
                }
            },
            "optional": {
                "creator": "some software package v1.0.1-35",
                "timestamp": -123123
            }
        }"""
        signature = json.loads(signature)
        errors = list(ve.message for ve in validator.iter_errors(signature))
        if not any("atomic container signature" in error for error in errors):
            self.fail("An invalid value for the field 'type' was not identified")
        if not any("-123123" in error for error in errors):
            self.fail("An invalid value for the field 'timestamp' was not identified")


class TestOCISchema(TestCase):
    """A test case for validating the OCI MANIFEST JSON schema."""

    def test_valid_manifest(self):
        """Check if a valid OCI manifest is successfully parsed."""
        manifest = """{
          "schemaVersion": 2,
          "mediaType": "application/vnd.oci.image.manifest.v1+json",
          "config": {
            "mediaType": "application/vnd.oci.image.config.v1+json",
            "size": 6641,
            "digest": "sha256:07652f42c464e19a7829b0495f4f1efc3eb41d8368da4ec9305cb59b3bd3e366"
          },
          "layers": [
            {
              "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
              "size": 50215654,
              "digest": "sha256:f7b061e2cdcce41364a408e8b449b7344e33b5bff9bbb935a97e1967db982c6d"
            }
          ]
        }"""
        manifest = json.loads(manifest)
        try:
            validate_manifest(manifest, MEDIA_TYPE.MANIFEST_OCI, "")
        except ManifestInvalid:
            self.fail()

    def test_valid_manifest_with_invalid_config_media_type(self):
        """Check if a manifest with an invalid config.mediaType is ignored instead of erroring."""
        manifest = """{
          "schemaVersion": 2,
          "mediaType": "application/vnd.oci.image.manifest.v1+json",
          "config": {
            "mediaType": "application/INVALID",
            "size": 6641,
            "digest": "sha256:07652f42c464e19a7829b0495f4f1efc3eb41d8368da4ec9305cb59b3bd3e366"
          },
          "layers": [
            {
              "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
              "size": 50215654,
              "digest": "sha256:f7b061e2cdcce41364a408e8b449b7344e33b5bff9bbb935a97e1967db982c6d"
            }
          ]
        }"""
        manifest = json.loads(manifest)
        try:
            validate_manifest(manifest, MEDIA_TYPE.MANIFEST_OCI, "")
        except ManifestInvalid:
            self.fail()

    def test_valid_manifest_with_invalid_layer_media_type(self):
        """Check if a manifest with an invalid layers[].mediaType is ignored instead of erroring."""
        manifest = """{
          "schemaVersion": 2,
          "mediaType": "application/vnd.oci.image.manifest.v1+json",
          "config": {
            "mediaType": "application/vnd.oci.image.config.v1+json",
            "size": 6641,
            "digest": "sha256:07652f42c464e19a7829b0495f4f1efc3eb41d8368da4ec9305cb59b3bd3e366"
          },
          "layers": [
            {
              "mediaType": "application/INVALID",
              "size": 50215654,
              "digest": "sha256:f7b061e2cdcce41364a408e8b449b7344e33b5bff9bbb935a97e1967db982c6d"
            }
          ]
        }"""
        manifest = json.loads(manifest)
        try:
            validate_manifest(manifest, MEDIA_TYPE.MANIFEST_OCI, "")
        except ManifestInvalid:
            self.fail()
