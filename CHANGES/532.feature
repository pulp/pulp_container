Added a limit of 4MB to Manifests and Signatures, through the `MANIFEST_PAYLOAD_MAX_SIZE` and 
`SIGNATURE_PAYLOAD_MAX_SIZE` settings, to protect against OOM DoS attacks.
