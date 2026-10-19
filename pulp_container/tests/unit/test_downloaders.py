import pytest

from pulp_container.app.downloaders import RegistryAuthHttpDownloader


@pytest.mark.parametrize(
    "header,expected",
    [
        (
            'Bearer realm="https://auth.docker.io/token",service="registry.docker.io"',
            {"realm": "https://auth.docker.io/token", "service": "registry.docker.io"},
        ),
        (
            'Bearer realm="https://gcr.io/v2/token",service=gcr.io',
            {"realm": "https://gcr.io/v2/token", "service": "gcr.io"},
        ),
        (
            'Bearer realm="https://quay.io/v2/auth",service="quay.io",'
            'scope="repository:foo/bar:pull,push"',
            {
                "realm": "https://quay.io/v2/auth",
                "service": "quay.io",
                "scope": "repository:foo/bar:pull,push",
            },
        ),
        (
            'Bearer realm="https://example.com/token", service=example.com, error="a \\"b\\""',
            {"realm": "https://example.com/token", "service": "example.com", "error": 'a "b"'},
        ),
    ],
)
def test_parse_auth_challenge(header, expected):
    assert RegistryAuthHttpDownloader.parse_auth_challenge(header) == expected
