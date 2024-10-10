# Limit the size of Manifests and Signatures

By default, Pulp is configured to block the synchronization and upload of image Manifests and/or
Signatures if they exceed a 4MB size limit. A use case for this feature is to avoid OOM DoS attacks
when synchronizing remote repositories with malicious or compromised container images.
To define a different limit, use the following settings:
```
MANIFEST_PAYLOAD_MAX_SIZE=<bytes>
SIGNATURE_PAYLOAD_MAX_SIZE=<bytes>
```

for example, to modify the limits to 10MB:
```
MANIFEST_PAYLOAD_MAX_SIZE=10_000_000
SIGNATURE_PAYLOAD_MAX_SIZE=10_000_000
```