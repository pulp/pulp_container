import aiohttp
import asyncio
import fnmatch
import json
import re

from aiohttp.client_exceptions import ClientResponseError
from collections import namedtuple
from django.conf import settings
from logging import getLogger
from urllib import parse


from pulpcore.plugin.download import DownloaderFactory, HttpDownloader

from pulp_container.constants import (
    MANIFEST_MEDIA_TYPES,
    MEGABYTE,
    V2_ACCEPT_HEADERS,
)
from pulp_container.app.exceptions import PayloadTooLarge

log = getLogger(__name__)

HeadResult = namedtuple(
    "HeadResult",
    ["status_code", "path", "artifact_attributes", "url", "headers"],
)
DownloadResult = namedtuple("DownloadResult", ["url", "artifact_attributes", "path", "headers"])


class ValidateResourceSizeMixin:
    async def _handle_response(self, response, content_type=None, max_body_size=None):
        """
        Overrides the HttpDownloader method to be able to limit the request body size.
        Handle the aiohttp response by writing it to disk and calculating digests
        Args:
            response (aiohttp.ClientResponse): The response to handle.
            content_type (string): Type of the resource (manifest or signature) whose size
                                   will be verified
            max_body_size (int): Maximum allowed body size of the resource (manifest or signature).
        Returns:
             DownloadResult: Contains information about the result. See the DownloadResult docs for
                 more information.
        """
        if self.headers_ready_callback:
            await self.headers_ready_callback(response.headers)
        total_size = 0
        while True:
            chunk = await response.content.read(MEGABYTE)
            total_size += len(chunk)
            if max_body_size and total_size > max_body_size:
                await self.finalize()
                raise PayloadTooLarge()
            if not chunk:
                await self.finalize()
                break  # the download is done
            await self.handle_data(chunk)
        return DownloadResult(
            path=self.path,
            artifact_attributes=self.artifact_attributes,
            url=self.url,
            headers=response.headers,
        )

    def get_content_type_and_max_resource_size(self, response):
        """
        Returns the content_type (manifest or signature) based on the HTTP request and also the
        corresponding resource allowed maximum size.
        """
        max_resource_size = None
        content_type = response.content_type
        is_cosign_tag = fnmatch.fnmatch(response.url.name, "sha256-*.sig")
        if isinstance(self, NoAuthSignatureDownloader) or is_cosign_tag:
            max_resource_size = settings["SIGNATURE_PAYLOAD_MAX_SIZE"]
            content_type = "Signature"
        elif content_type in MANIFEST_MEDIA_TYPES.IMAGE + MANIFEST_MEDIA_TYPES.LIST:
            max_resource_size = settings["MANIFEST_PAYLOAD_MAX_SIZE"]
            content_type = "Manifest"
        return content_type, max_resource_size


class RegistryAuthHttpDownloader(ValidateResourceSizeMixin, HttpDownloader):
    """
    Custom Downloader that automatically handles Token Based and Basic Authentication.

    Additionally, use custom headers from DeclarativeArtifact.extra_data['headers']
    """

    registry_auth = {"bearer": None, "basic": None}
    token_lock = asyncio.Lock()

    def __init__(self, *args, **kwargs):
        """
        Initialize the downloader.
        """
        self.remote = kwargs.pop("remote")

        super().__init__(*args, **kwargs)

    async def _run(self, handle_401=True, extra_data=None):
        """
        Download, validate, and compute digests on the `url`. This is a coroutine.

        This method is externally wrapped with backoff-and-retry behavior for some errors.
        It retries with exponential backoff some number of times before allowing a final
        exception to be raised.

        This method provides the same return object type and documented in
        :meth:`~pulpcore.plugin.download.BaseDownloader._run`.

        Args:
            handle_401(bool): If true, catch 401, request a new token and retry.

        """
        # manifests are header sensitive, blobs do not care
        # these accept headers are going to be sent with every request to ensure downloader
        # can download manifests, namely in the repair core task
        # FIXME this can be rolledback after https://github.com/pulp/pulp_container/issues/1288
        headers = V2_ACCEPT_HEADERS
        repo_name = None
        if extra_data is not None:
            headers = extra_data.get("headers", headers)
            repo_name = extra_data.get("repo_name", None)
        http_method = extra_data.get("http_method", "get") if extra_data is not None else "get"
        this_token = self.registry_auth["bearer"]
        basic_auth = self.registry_auth["basic"]
        auth_headers = self.auth_header(this_token, basic_auth)
        headers.update(auth_headers)
        # aiohttps does not allow to send auth argument and auth header together
        self.session._default_auth = None
        if self.download_throttler:
            await self.download_throttler.acquire()

        session_http_method = getattr(self.session, http_method)

        async with session_http_method(
            self.url, headers=headers, proxy=self.proxy, proxy_auth=self.proxy_auth
        ) as response:
            try:
                response.raise_for_status()
            except ClientResponseError as e:
                response_auth_header = response.headers.get("www-authenticate")
                # Need to retry request
                if handle_401 and e.status == 401 and response_auth_header is not None:
                    # check if bearer or basic
                    if "Bearer" in response_auth_header:
                        # Token has not been updated during request
                        if (
                            self.registry_auth["bearer"] is None
                            or self.registry_auth["bearer"] == this_token
                        ):
                            self.registry_auth["bearer"] = None
                            await self.update_token(response_auth_header, this_token, repo_name)
                        return await self._run(handle_401=False, extra_data=extra_data)
                    elif "Basic" in response_auth_header:
                        if self.remote.username:
                            basic = aiohttp.BasicAuth(self.remote.username, self.remote.password)
                            self.registry_auth["basic"] = basic.encode()
                        return await self._run(handle_401=False, extra_data=extra_data)
                else:
                    raise

            if http_method == "head":
                to_return = await self._handle_head_response(response)
            else:
                content_type, max_resource_size = self.get_content_type_and_max_resource_size(
                    response
                )
                to_return = await self._handle_response(response, content_type, max_resource_size)

            await response.release()
            self.response_headers = response.headers

        if self._close_session_on_finalize:
            self.session.close()
        return to_return

    async def update_token(self, response_auth_header, used_token, repo_name):
        """
        Update the Bearer token to be used with all requests.
        """
        async with self.token_lock:
            if (
                self.registry_auth["bearer"] is not None
                and self.registry_auth["bearer"] == used_token
            ):
                return
            log.info("Updating bearer token")
            bearer_info_string = response_auth_header[len("Bearer ") :]
            bearer_info_list = re.split(",(?=[^=,]+=)", bearer_info_string)

            # The remaining string consists of comma seperated key=value pairs
            auth_query_dict = {}
            for key, value in (item.split("=") for item in bearer_info_list):
                # The value is a string within a string, ex: '"value"'
                auth_query_dict[key] = json.loads(value)
            try:
                token_base_url = auth_query_dict.pop("realm")
            except KeyError:
                raise IOError("No realm specified for token auth challenge.")

            # self defense strategy in cases when registry does not provide the scope
            if "scope" not in auth_query_dict:
                auth_query_dict["scope"] = "repository:{0}:pull".format(repo_name)

            # Construct a url with query parameters containing token auth challenge info
            parsed_url = parse.urlparse(token_base_url)
            # Add auth query params to query dict and urlencode into a string
            new_query = parse.urlencode({**parse.parse_qs(parsed_url.query), **auth_query_dict})
            updated_parsed = parsed_url._replace(query=new_query)
            token_url = parse.urlunparse(updated_parsed)
            headers = {}
            if self.remote.username:
                # for private repos
                basic = aiohttp.BasicAuth(self.remote.username, self.remote.password).encode()
                headers["Authorization"] = basic
            async with self.session.get(
                token_url,
                headers=headers,
                proxy=self.proxy,
                proxy_auth=self.proxy_auth,
                raise_for_status=True,
            ) as token_response:
                token_data = await token_response.text()

            token_js = json.loads(token_data)
            token = token_js.get("token") or token_js.get("access_token")
            self.registry_auth["bearer"] = token

    @staticmethod
    def auth_header(token, basic_auth):
        """
        Create an auth header that optionally includes a bearer token or basic auth.

        Args:
            auth (str): Bearer token or Basic auth to use in header

        Returns:
            dictionary: containing Authorization headers or {} if Authorizationis is None.

        """
        if token is not None:
            return {"Authorization": "Bearer {token}".format(token=token)}
        elif basic_auth is not None:
            return {"Authorization": basic_auth}
        return {}

    async def _handle_head_response(self, response):
        return HeadResult(
            status_code=response.status,
            path=None,
            artifact_attributes=None,
            url=self.url,
            headers=response.headers,
        )


class NoAuthSignatureDownloader(ValidateResourceSizeMixin, HttpDownloader):
    """A downloader class suited for signature downloads."""

    def raise_for_status(self, response):
        """Log an error only if the status code of the response is not equal to 404.

        Status codes equal to 404 signify that a signature could not be found on the server. This
        case is still valid because it is not possible to determine the number of signatures
        beforehand.
        """
        if response.status == 404:
            raise FileNotFoundError()
        else:
            response.raise_for_status()

    async def _run(self, extra_data=None):
        if self.download_throttler:
            await self.download_throttler.acquire()
        async with self.session.get(
            self.url, proxy=self.proxy, proxy_auth=self.proxy_auth, auth=self.auth
        ) as response:
            self.raise_for_status(response)
            content_type, max_resource_size = self.get_content_type_and_max_resource_size(response)
            to_return = await self._handle_response(response, content_type, max_resource_size)
            await response.release()
        if self._close_session_on_finalize:
            await self.session.close()
        return to_return


class NoAuthDownloaderFactory(DownloaderFactory):
    """
    A downloader factory without any preset auth configuration, TLS or basic auth.
    """

    def _http_or_https(self, download_class, url, **kwargs):
        """
        Same as DownloaderFactory._http_or_https, excluding the basic auth credentials.

        Args:
            download_class (:class:`~pulpcore.plugin.download.BaseDownloader`): The download
                class to be instantiated.
            url (str): The download URL.
            kwargs (dict): All kwargs are passed along to the downloader. At a minimum, these
                include the :class:`~pulpcore.plugin.download.BaseDownloader` parameters.

        Returns:
            :class:`~pulpcore.plugin.download.HttpDownloader`: A downloader that
            is configured with the remote settings.

        """
        options = {"session": self._session}
        if self._remote.proxy_url:
            options["proxy"] = self._remote.proxy_url
            if self._remote.proxy_username and self._remote.proxy_password:
                options["proxy_auth"] = aiohttp.BasicAuth(
                    login=self._remote.proxy_username, password=self._remote.proxy_password
                )

        kwargs["throttler"] = self._remote.download_throttler if self._remote.rate_limit else None

        return download_class(url, **options, **kwargs)
