Pull-through manifest resolution now performs a HEAD-based version check and serves locally
stored manifests without downloading the manifest body. Per Docker Hub's pull definition, version
checks do not count toward rate limits, substantially reducing 429 errors for repeat tag
resolutions.
