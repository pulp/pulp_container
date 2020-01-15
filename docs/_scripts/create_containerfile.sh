#!/usr/bin/env bash

echo "Create a Containerfile that expects foo/bar/example.txt inside /pulp_working_directory."

echo 'FROM centos:7

# Copy a file using RUN statement (absolute path required)
RUN cp /pulp_working_directory/foo/bar/example.txt /

# Copy a file using COPY statement (relative path can be used)
COPY foo/bar/example.txt /inside-image.txt

# Print the content of the file when the container starts
CMD ["cat", "/inside-image.txt"]' >> Containerfile