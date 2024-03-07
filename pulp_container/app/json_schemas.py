from pulp_container.constants import (
    BLOB_CONTENT_TYPE,
    MEDIA_TYPE,
    SIGNATURE_TYPE,
)


def get_descriptor_schema(
    allowed_media_types=None, additional_properties=None, additional_required=None
):
    """Return a concrete descriptor schema for manifests."""

    media_type_config = {"type": "string"}
    if allowed_media_types is not None:
        media_type_config = {"type": "string", "enum": allowed_media_types}

    properties = {
        "mediaType": media_type_config,
        "size": {"type": "number"},
        "digest": {"type": "string"},
        "annotations": {"type": "object", "additionalProperties": True},
        "urls": {
            "type": "array",
            "items": {"type": "string"},
            "format": "uri",
            "pattern": "^https?://",
        },
        "data": {"type": "string", "contentEncoding": "base64"},
        "artifactType": {"type": "string"},
    }

    if additional_properties:
        properties.update(additional_properties)

    required = ["mediaType", "size", "digest"]
    if additional_required:
        required.extend(additional_required)

    return {"type": "object", "properties": properties, "required": required}


OCI_INDEX_SCHEMA = {
    "type": "object",
    "properties": {
        "schemaVersion": {"type": "number", "minimum": 2, "maximum": 2},
        "mediaType": {
            "type": "string",
            "enum": [MEDIA_TYPE.INDEX_OCI],
        },
        "manifests": {
            "type": "array",
            "items": get_descriptor_schema(
                allowed_media_types=[
                    MEDIA_TYPE.MANIFEST_OCI,
                    MEDIA_TYPE.INDEX_OCI,
                    MEDIA_TYPE.MANIFEST_V2,
                    MEDIA_TYPE.MANIFEST_LIST,
                ],
                additional_properties={
                    "platform": {
                        "type": "object",
                        "properties": {
                            "architecture": {"type": "string"},
                            "os": {"type": "string"},
                            "os.version": {"type": "string"},
                            "os.features": {"type": "array", "items": {"type": "string"}},
                            "variant": {"type": "string"},
                            "features": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["architecture", "os"],
                    },
                },
                additional_required=["platform"],
            ),
        },
        "subject": get_descriptor_schema(),
        "annotations": {"type": "object", "additionalProperties": True},
    },
    "required": ["schemaVersion", "manifests"],
}


OCI_MANIFEST_SCHEMA = {
    "type": "object",
    "properties": {
        "schemaVersion": {"type": "number", "minimum": 2, "maximum": 2},
        "mediaType": {
            "type": "string",
            "enum": [MEDIA_TYPE.MANIFEST_OCI],
        },
        "artifactType": {"type": "string"},
        "config": get_descriptor_schema(),
        "layers": {
            "type": "array",
            "items": get_descriptor_schema(),
        },
        "subject": get_descriptor_schema(),
        "annotations": {"type": "object", "additionalProperties": True},
    },
    "required": ["schemaVersion", "config", "layers"],
    "if": {
        "properties": {
            "config": {"properties": {"mediaType": {"const": MEDIA_TYPE.OCI_EMPTY_JSON}}}
        }
    },
    "then": {"dependentRequired": {"config.mediaType": ["artifactType"]}},
}


DOCKER_MANIFEST_LIST_V2_SCHEMA = {
    "type": "object",
    "properties": {
        "schemaVersion": {"type": "number", "minimum": 2, "maximum": 2},
        "mediaType": {
            "type": "string",
            "enum": [MEDIA_TYPE.MANIFEST_LIST],
        },
        "manifests": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "mediaType": {
                        "type": "string",
                        "enum": [
                            MEDIA_TYPE.MANIFEST_V2,
                            MEDIA_TYPE.MANIFEST_V1,
                        ],
                    },
                    "size": {"type": "number"},
                    "digest": {"type": "string"},
                    "platform": {
                        "type": "object",
                        "properties": {
                            "architecture": {"type": "string"},
                            "os": {"type": "string"},
                            "os.version": {"type": "string"},
                            "os.features": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "variant": {"type": "string"},
                            "features": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": ["architecture", "os"],
                    },
                },
                "required": ["mediaType", "size", "digest", "platform"],
            },
        },
    },
    "required": ["schemaVersion", "mediaType", "manifests"],
}


DOCKER_MANIFEST_V2_SCHEMA = {
    "type": "object",
    "properties": {
        "schemaVersion": {"type": "number", "minimum": 2, "maximum": 2},
        "mediaType": {
            "type": "string",
            "enum": [MEDIA_TYPE.MANIFEST_V2],
        },
        "config": {
            "type": "object",
            "properties": {
                "mediaType": {
                    "type": "string",
                    "enum": [MEDIA_TYPE.CONFIG_BLOB, BLOB_CONTENT_TYPE],
                },
                "size": {"type": "number"},
                "digest": {"type": "string"},
            },
            "required": ["mediaType", "size", "digest"],
        },
        "layers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "mediaType:": {
                        "type": "string",
                        "enum": [
                            MEDIA_TYPE.REGULAR_BLOB,
                            MEDIA_TYPE.FOREIGN_BLOB,
                        ],
                    },
                    "size": {"type": "number"},
                    "digest": {"type": "string"},
                },
                "required": ["mediaType", "size", "digest"],
            },
        },
    },
    "required": ["schemaVersion", "mediaType", "config", "layers"],
}


DOCKER_MANIFEST_V1_SCHEMA = {
    "type": "object",
    "properties": {
        "signatures": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "protected": {"type": "string"},
                    "header": {
                        "type": "object",
                        "properties": {"alg": {"type": "string"}, "jwk": {"type": "object"}},
                        "required": ["alg", "jwk"],
                    },
                    "signature": {"type": "string"},
                },
                "required": ["protected", "header", "signature"],
            },
        },
        "tag": {"type": "string"},
        "name": {"type": "string"},
        "history": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"v1Compatibility": {"type": "string"}},
                "required": ["v1Compatibility"],
            },
        },
        "fsLayers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"blobSum": {"type": "string"}},
                "required": ["blobSum"],
            },
        },
    },
    "required": ["tag", "name", "fsLayers", "history"],
}


SIGNATURE_SCHEMA = {
    "title": "Atomic Container Signature",
    "description": "JSON Schema Validation for the Signature Payload",
    "type": "object",
    "properties": {
        "critical": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "const": SIGNATURE_TYPE.ATOMIC_FULL},
                "image": {
                    "type": "object",
                    "properties": {"docker-manifest-digest": {"type": "string"}},
                    "required": ["docker-manifest-digest"],
                    "additionalProperties": False,
                },
                "identity": {
                    "type": "object",
                    "properties": {"docker-reference": {"type": "string"}},
                    "required": ["docker-reference"],
                    "additionalProperties": False,
                },
            },
            "required": ["type", "image", "identity"],
            "additionalProperties": False,
        },
        "optional": {
            "type": "object",
            "properties": {
                "creator": {"type": "string"},
                "timestamp": {"type": "number", "minimum": 0},
            },
        },
    },
    "required": ["critical", "optional"],
    "additionalProperties": False,
}
