Managing additional OCI media types
===================================

.. _default-oci-types:

Pulp is not only a container registry, it also supports OCI artifacts by leveraging the config property on the image manifest.
Here are some examples of compliant OCI artifacts supported by `pulp_container` plugin::

 * [OCI images](./workflows/build-containerfile.rst)
 * [Helm](./workflows/helm-support.rst)
 * [Flatpak images](./workflows/flatpak-support.rst)
 * [Cosign, SBOMs, attestations](./workflows/cosign-support.rst)
 * Source containers
 * Singularity
 * Conftest policies
 * WASM
