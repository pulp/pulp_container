# Build Images

!!! warning

    All container build APIs are in tech preview. Backwards compatibility when upgrading is not
    guaranteed.

Users can add new images to a container repository by uploading a Containerfile. The syntax for
Containerfile is the same as for a Dockerfile.

To pass arbitrary files or artifacts to the image building context, the `build_context` property (a reference to a file repository) can be provided in the request payload.
These files can be referenced in Containerfile by passing their `relative-path`:
```
ADD/COPY <file relative-path> <location in container>
```

It is possible to define the Containerfile in two ways:
* from a [local file](site:pulp_container/docs/admin/guides/build-image#build-from-a-containerfile-uploaded-during-build-request) and pass it during build request
* from an [existing file](site:pulp_container/docs/admin/guides/build-image#upload-the-containerfile-as-a-file-content) in the `build_context`

## Create a Container Repository

```bash
CONTAINER_REPO=$(pulp container repository create --name building | jq -r '.pulp_href')
```

## Create a File Repository and populate it

```bash
FILE_REPO=$(pulp file repository create --name bar --autopublish | jq -r '.pulp_href')

echo 'Hello world!' > example.txt

pulp file content upload --relative-path foo/bar/example.txt \
--file ./example.txt --repository bar
```

## Create a Containerfile

```bash
echo 'FROM centos:7

# Copy a file using COPY statement. Use the path specified in the '--relative-path' parameter.
COPY foo/bar/example.txt /inside-image.txt

# Print the content of the file when the container starts
CMD ["cat", "/inside-image.txt"]' >> Containerfile
```


## Build from a Containerfile uploaded during build request

```bash
TASK_HREF=$(http --form POST ${BASE_ADDR}${CONTAINER_REPO}'build_image/' "containerfile@./Containerfile" \
build_context=${FILE_REPO}versions/1/ | jq -r '.task')
```

## Upload the Containerfile to a File Repository and use it to build

### Upload the Containerfile as a File Content

```bash
pulp file content upload --relative-path MyContainerfile --file ./Containerfile --repository bar
```

### Build an OCI image from a Containerfile present in build_context

```bash
TASK_HREF=$(http --form POST ${BASE_ADDR}${CONTAINER_REPO}'build_image/' containerfile_name=MyContainerfile \
build_context=${FILE_REPO}versions/2/ | jq -r '.task')
```


!!! warning

    File repositories synced with the on-demand policy will not automatically download the missing artifacts.
    Trying to build an image using a file that has not yet been downloaded will fail.
