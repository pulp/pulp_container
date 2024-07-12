# Limit the size of Manifests and Signatures

By default, Pulp is configured to block the synchronization of non-Blob content (Manifests,
Signatures, etc.) if they exceed a 4MB size limit. A use case for this feature is to avoid
OOM DoS attacks when synchronizing remote repositories with malicious or compromised container
images.
To define a different limit, use the following setting:
```
OCI_PAYLOAD_MAX_SIZE=<bytes>
```

for example, to modify the limit to 10MB:
```
OCI_PAYLOAD_MAX_SIZE=10_000_000
```