# Overview

The Pulp Container plugin extends Pulp so that you can host your container registry and distribute containers in an on-premises environment.
Pulp is a Container and Artifact Registry that implements [OCI Distribution Specification](https://github.com/opencontainers/distribution-spec/)
and [OCI Image Format Specification](https://github.com/opencontainers/image-spec).
On top of the standard registry capabilites, Pulp Registry provides additional features. For example, you can synchronize from any Container Registry that is HTTP API V2-compatible.
Depending on your needs, you can perform whole or partial syncs from these remote repositories, blend content from different sources, and distribute them throughout your organization using Pulp.
You can also build OCI-compatible images with Pulp Container and push them to a repository in Pulp so you can distribute private containers.

For information about why you might think about hosting your own container registry, see [5 reasons to host your container registry with Pulp](https://opensource.com/article/21/5/container-management-pulp/). At the time of this article's publication, there was no native way to perform import and exports to disconnected or air-gapped environments. This has since been introduced and is available.

If you'd like to watch a recent talk about Pulp Container and see it in action, check out [Registry Native Delivery of Software Content](https://video.fosdem.org/2021/D.infra/registrynativedeliverysoftwarecontentpulp3.mp4).

## Features

- Synchronize container image repositories hosted on Docker-hub, Google Container Registry,
  Quay.io, etc., in mirror or additive mode
- Automatically create Versioned Repositories so every operation is a restorable snapshot
- Download content on-demand when requested by clients to reduce disk space
- Perform docker/podman pull from a container distribution served by Pulp
- Perform docker/podman push to the Pulp Registry
- Curate container images by filtering what is mirrored from an external repository
- Curate container images by creating repository versions with a specific set of images
- Build an OCI format image from a Containerfile and make it available from the Pulp Registry
- Host content either locally or on S3
- De-duplicate all saved content
- Support disconnected and air-gapped environments with the Pulp Import/Export facility for container repositories
- Host Flatpak content in OCI format
- Host Helm Charts
- Host OCI artifacts
- Sign images and host Cosign signatures, SBOMS and attestations
- Sign images and host Atomic signature type via extensions API
- Host content via pull-through caching distributions
- Discover and replicate distributions to serve the same content as the upstream Pulp
