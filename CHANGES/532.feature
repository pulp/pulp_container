Added a limit of 4MB to non-Blob content, through the `OCI_PAYLOAD_MAX_SIZE` setting, to protect
against OOM DoS attacks.
