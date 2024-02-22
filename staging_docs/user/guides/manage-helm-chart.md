# Manage Helm Charts

Helm charts are packages for Kubernetes applications, bundling YAML files defining resources like
deployments and services. To package them as container images, developers use tools like Helm to
embed the application code and dependencies into a containerized environment. Container registries
provide platforms for storing and sharing these containerized Helm charts, simplifying deployment
across Kubernetes clusters.

## Push and Host

Use the following **example** to download and push an etherpad chart from the Red Hat community repository.

Add a chart repository:

```
helm repo add redhat-cop https://redhat-cop.github.io/helm-charts
```

Update the information of available charts locally from the chart repository:

```
helm repo update
```

Download a chart from a repository:

```
helm pull redhat-cop/etherpad --version=0.0.4 --untar
```

Package the chart into a chart archive:

```
helm package ./etherpad
```

Log in to your Pulp container registry using helm registry login:

```
helm registry login pulp3-source-fedora36.puffy.example.com
```

Push the chart to your Pulp Container registry using the helm push command:

=== "Script"

    ```
    helm push etherpad-0.0.4.tgz oci://pulp3-source-fedora36.puffy.example.com
    ```

=== "Output"

    ```
    Pushed: pulp3-source-fedora36.puffy.example.com/etherpad:0.0.4
    Digest: sha256:a6667ff2a0e2bd7aa4813db9ac854b5124ff1c458d170b70c2d2375325f2451b
    ```

Ensure that the push worked by deleting the local copy, and then pulling the chart from the repository:

=== "Script"

    ```
    rm -rf etherpad-0.0.4.tgz

    helm pull oci://pulp3-source-fedora36.puffy.example.com/etherpad --version 0.0.4
    ```

=== "Script"

    ```
    Pulled: pulp3-source-fedora36.puffy.example.com/etherpad:0.0.4
    Digest: sha256:4f627399685880daf30cf77b6026dc129034d68c7676c7e07020b70cf7130902
    ```

The chart can then be installed using the helm install command:

```
helm install etherpad-0.0.4.tgz
```

Alternatively, charts can be installed directly from the registry without needing to download locally.
Use the helm install command and reference the registry location:

```
helm install oci://pulp3-source-fedora36.puffy.example.com/helm/etherpad --version=0.0.4
```

## Mirror

Being an OCI compliant registry, Pulp Container registry can natively mirror helm charts
that are stored as an OCI image:

```
{
 "schemaVersion": 2,
 "config": {
   "mediaType": "application/vnd.cncf.helm.config.v1+json",
   "digest": "sha256:8ec7c0f2f6860037c19b54c3cfbab48d9b4b21b485a93d87b64690fdb68c2111",
   "size": 117
 },
 "layers": [
   {
     "mediaType": "application/vnd.cncf.helm.chart.content.v1.tar+gzip",
     "digest": "sha256:1b251d38cfe948dfc0a5745b7af5ca574ecb61e52aed10b19039db39af6e1617",
     "size": 2487
   },
   {
     "mediaType": "application/vnd.cncf.helm.chart.provenance.v1.prov",
     "digest": "sha256:3e207b409db364b595ba862cdc12be96dcdad8e36c59a03b7b3b61c946a5741a",
     "size": 643
   }
 ]
}
```
