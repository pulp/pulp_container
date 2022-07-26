import json

from jsonschema import Draft7Validator

from django.test import TestCase

from pulp_container.app.json_schemas import SIGNATURE_SCHEMA

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
