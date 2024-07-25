# Build Images

!!! warning

    All container build APIs are in tech preview. Backwards compatibility when upgrading is not
    guaranteed.

Users can add new images to a container repository by uploading a Containerfile. The syntax for
Containerfile is the same as for a Dockerfile. The same REST API endpoint also accepts a JSON
string that maps artifacts in Pulp to a filename. Any artifacts passed in are available inside the
build container at `/pulp_working_directory`.

## Create a Repository

```bash
REPO_HREF=$(pulp container repository create --name building | jq -r '.pulp_href')
```

## Create an Artifact

```bash
echo 'Hello world!' > example.txt

ARTIFACT_HREF=$(http --form POST http://localhost/pulp/api/v3/artifacts/ \
    file@./example.txt \
    | jq -r '.pulp_href')
```

## Create a Containerfile

```bash
echo 'FROM centos:7

# Copy a file using COPY statement. Use the relative path specified in the 'artifacts' parameter.
COPY foo/bar/example.txt /inside-image.txt

# Print the content of the file when the container starts
CMD ["cat", "/inside-image.txt"]' >> Containerfile
```

## Build an OCI image

```bash
TASK_HREF=$(http --form POST :$REPO_HREF'build_image/' containerfile@./Containerfile \
artifacts="{\"$ARTIFACT_HREF\": \"foo/bar/example.txt\"}"  | jq -r '.task')
```

!!! warning

    Non-staff users, lacking read access to the `artifacts` endpoint, may encounter restricted
    functionality as they are prohibited from listing artifacts uploaded to Pulp and utilizing
    them within the build process.
