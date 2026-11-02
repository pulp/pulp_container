Added tag list bypass optimization for digest-based sync. When all entries in a remote's
``includes`` field are sha256 digests (or ``name=sha256:digest`` aliases), the sync pipeline
skips the expensive ``/tags/list`` enumeration and fetches manifests directly by digest.
This reduces sync time from minutes to seconds for repositories with tens of thousands of tags
(e.g., ``openshift-release-dev/ocp-v4.0-art-dev`` with 50,000+ tags). Named aliases
(``name=sha256:digest``) create human-readable tags alongside the digest, enabling friendly
image references in disconnected environments. Added ``auto_discover_cosign`` field on
``ContainerRemote`` to control automatic cosign companion tag discovery via HEAD probes
when the tag list is bypassed.
