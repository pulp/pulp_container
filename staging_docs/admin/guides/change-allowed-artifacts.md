# Configure Supported OCI Types

By default, the following list of media types is enabled in the Container Registry:

* OCI images
* Helm
* Cosign, SBOMs, attestations
* Source containers
* Singularity
* Conftest policies
* WASM

For any other OCI media type that is not supported by default, you can add them to the
`ADDITIONAL_OCI_ARTIFACT_TYPES` setting using the following format:

```
ADDITIONAL_OCI_ARTIFACT_TYPES = {
   "<oci config type 1>": [
       "<oci layer type A>",
       "<oci layer type B>",
   ],
   "<oci config type 2>": [
       "<oci layer type C>",
       "<oci layer type D>",
   ],
}
```

For example, you can add support for custom defined mediatype by adding the following to your
`ADDITIONAL_OCI_ARTIFACT_TYPES` setting:

```
ADDITIONAL_OCI_ARTIFACT_TYPES = {
   "<oci config type 1>": [
       "<oci layer type A>",
       "<oci layer type B>",
   ],
   "<oci config type 2>": [
       "<oci layer type C>",
       "<oci layer type D>",
   ],
   "application/vnd.guardians.groot.config.v1+json": [
       "text/plain",
       "application/vnd.guardians.groot.docs.layer.v1+tar",
   ],
}

```

!!! note

    When adding OCI media types that are not configured by default, it is necessary then to manually add
    the `Default oci types<default-oci-types>` to the list.
    The OCI image-spec types are supported by default, they are built-in and cannot be disabled, it is
    not necessary to add them manually to the list.
