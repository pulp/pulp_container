SIGNATURE_SCHEMA = """{
    "$schema": "http://json-schema.org/draft-07/schema",
    "$id": "https://example.com/product.schema.json",
    "title": "Atomic Container Signature",
    "description": "JSON Schema Validation for the Signature Payload",
    "type": "object",
    "properties": {
        "critical": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "const": "atomic container signature"
                },
                "image": {
                    "type": "object",
                    "properties": {
                        "docker-manifest-digest": {
                            "type": "string"
                        }
                    },
                    "required": ["docker-manifest-digest"],
                    "additionalProperties": false
                },
                "identity": {
                    "type": "object",
                    "properties": {
                        "docker-reference": {
                            "type": "string"
                        }
                    },
                    "required": ["docker-reference"],
                    "additionalProperties": false
                }
            },
            "required": ["type", "image", "identity"],
            "additionalProperties": false
        },
        "optional": {
            "type": "object",
            "properties": {
                "creator": {
                    "type": "string"
                },
                "timestamp": {
                    "type": "number",
                    "minimum": 0
                }
            }
        }
    },
    "required": ["critical", "optional"],
    "additionalProperties": false
}"""
