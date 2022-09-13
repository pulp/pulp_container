from pulp_container.constants import MANIFEST_MEDIA_TYPES, MEDIA_TYPE


def get_accepted_media_types(headers):
    """
    Returns a list of media types from the Accept headers.

    Args:
        headers (:class:`~aiohttp.multidict.CIMultiDictProxy` or dict):
            The request's headers to extract accepted media types from.

    Returns:
        List of media types supported by the client.

    """
    accepted_media_types = []
    for header, values in headers.items():
        if header == "Accept":
            values = [v.strip() for v in values.split(",")]
            accepted_media_types.extend(values)
    return accepted_media_types


def determine_media_type(content_data, response):
    """Determine the media type of a manifest either from the JSON data or the response object."""
    if media_type := content_data.get("mediaType"):
        return media_type
    elif media_type := response.headers.get("content-type"):
        # translate v1 signed media_type
        if media_type == MEDIA_TYPE.MANIFEST_V1_SIGNED:
            return MEDIA_TYPE.MANIFEST_V1
        elif media_type in (MANIFEST_MEDIA_TYPES.IMAGE or MANIFEST_MEDIA_TYPES.LIST):
            return media_type
        else:
            pass
    return determine_media_type_from_json(content_data)


def determine_media_type_from_json(content_data):
    """Determine the media tpye of a manifest from the provided JSON data."""
    if media_type := content_data.get("mediaType"):
        return media_type
    elif manifests := content_data.get("manifests"):
        if len(manifests):
            if manifests[0].get("mediaType") in (MEDIA_TYPE.MANIFEST_V2, MEDIA_TYPE.MANIFEST_V1):
                return MEDIA_TYPE.MANIFEST_LIST
            elif manifests[0].get("mediaType") in (MEDIA_TYPE.MANIFEST_OCI, MEDIA_TYPE.INDEX_OCI):
                return MEDIA_TYPE.INDEX_OCI
        return MEDIA_TYPE.MANIFEST_LIST
    else:
        if config := content_data.get("config"):
            config_media_type = config.get("mediaType")
            if config_media_type == MEDIA_TYPE.CONFIG_BLOB_OCI:
                return MEDIA_TYPE.MANIFEST_OCI
            else:
                return MEDIA_TYPE.MANIFEST_V2
        else:
            return MEDIA_TYPE.MANIFEST_V1
