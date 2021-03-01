import base64
import json

from django.test import TestCase

from jwkest import jws

from pulp_container.app import schema_convert


class Test(TestCase):
    """Schema2toSchema1Converter test class"""

    def test_convert(self):
        """Test schema converter on a known manifest"""
        cnv = schema_convert.Schema2toSchema1Converter(
            MANIFEST, CONFIG_LAYER, "test-repo", "tes-tag"
        )
        converted_mf, signed_mf = cnv.convert()
        compare_manifests(converted_mf, signed_mf)
        validate_signature(signed_mf)

        empty = dict(blobSum=cnv.EMPTY_LAYER)
        assert [
            dict(blobSum="sha256:layer1"),
            empty,
            empty,
            empty,
            empty,
            dict(blobSum="sha256:base"),
        ] == cnv.fs_layers

    def test_manifest_with_foreign_layers_conversion(self):
        """Test if the conversion of a manifest with foreign layers fails gracefully"""
        try:
            schema_convert.Schema2toSchema1Converter(
                MANIFEST_WITH_FOREIGN_LAYERS, CONFIG_LAYER, "test-repo", "tes-tag"
            )
        except ValueError:
            pass
        else:
            assert False

    def test_compute_layers(self):
        """Test that computing the layers produces the expected data"""
        cnv = schema_convert.Schema2toSchema1Converter(
            MANIFEST, CONFIG_LAYER, "test-repo", "tes-tag"
        )
        cnv.compute_layers()
        empty = dict(blobSum=cnv.EMPTY_LAYER)
        assert [
            dict(blobSum="sha256:layer1"),
            empty,
            empty,
            empty,
            empty,
            dict(blobSum="sha256:base"),
        ] == cnv.fs_layers
        assert [
            {
                "v1Compatibility": '{"architecture":"amd64","author":"Mihai Ibanescu <mihai.ibanescu@gmail.com>","config":{"Cmd":["/bin/bash"],"Hostname":"decafbad"},"container_config":{"Hostname":"decafbad","Tty":false},"created":"2019-09-05T21:28:52.173079282Z","docker_version":"1.13.1","id":"8e1cc996a0d319582f770dbded72777c5b8c5c46859c506db5acc674bc42ee51","parent":"3d0d31cc2270f872e56b7b7e35fb4fb7796797a8979ae180a2baee7107a5eb5b"}'  # noqa
            },
            {
                "v1Compatibility": '{"container_config":{"Cmd":[""]},"created":"2019-09-05T21:28:46.173079282Z","id":"3d0d31cc2270f872e56b7b7e35fb4fb7796797a8979ae180a2baee7107a5eb5b","parent":"6474547c15d178825c70a42efdc59a88c6e30d764d184b415f32484562803446","throwaway":true}'  # noqa
            },
            {
                "v1Compatibility": '{"container_config":{"Cmd":["/bin/sh -c #(nop)  MAINTAINER Mihai Ibanescu <mihai.ibanescu@gmail.com>"]},"created":"2019-09-05T21:28:43.305854958Z","id":"6474547c15d178825c70a42efdc59a88c6e30d764d184b415f32484562803446","parent":"5708420291e0a86d8dc08ec40b2c1b1799117c33fe85032b87227632f70c1018","throwaway":true}'  # noqa
            },
            {
                "v1Compatibility": '{"container_config":{"Cmd":["/bin/sh -c #(nop)  CMD [\\"/bin/bash\\"]"]},"created":"2018-03-06T00:48:12.679169547Z","id":"5708420291e0a86d8dc08ec40b2c1b1799117c33fe85032b87227632f70c1018","parent":"9e9220abceaf86f2ad7820ae8124d01223d8ec022b9a6cb8c99a8ae1747137ea","throwaway":true}'  # noqa
            },
            {
                "v1Compatibility": '{"container_config":{"Cmd":["/bin/sh -c #(nop)  LABEL name=CentOS Base Image vendor=CentOS license=GPLv2 build-date=20180302"]},"created":"2018-03-06T00:48:12.458578213Z","id":"9e9220abceaf86f2ad7820ae8124d01223d8ec022b9a6cb8c99a8ae1747137ea","parent":"cb48c1db9c0a1ede7c85c85351856fc3e40e750931295c8fac837c63b403586a","throwaway":true}'  # noqa
            },
            {
                "v1Compatibility": '{"container_config":{"Cmd":["/bin/sh -c #(nop) ADD file:FILE_CHECKSUM in / "]},"created":"2018-03-06T00:48:12.077095981Z","id":"cb48c1db9c0a1ede7c85c85351856fc3e40e750931295c8fac837c63b403586a"}'  # noqa
            },
        ] == cnv.history


def compare_manifests(converted_mf, signed_mf):
    """
    Compare the manifests without signatures.
    """
    converted_mf_json = json.loads(converted_mf)
    signed_mf_json = json.loads(signed_mf)

    signed_mf_json.pop("signatures")

    assert converted_mf_json == signed_mf_json


def validate_signature(signed_mf):
    """
    Validate the signature of a signed manifest

    A signed manifest is a JSON document with a signature attribute
    as the last element.
    """
    # In order to validate the signature, we need the exact original payload
    # (the document without the signature). We cannot json.load the document
    # and get rid of the signature, the payload would likely end up
    # differently because of differences in field ordering and indentation.
    # So we need to strip the signature using plain string manipulation, and
    # add back a trailing }

    # strip the signature block
    payload, sep, signatures = signed_mf.partition('   "signatures"')
    # get rid of the trailing ,\n, and add \n}
    jw_payload = payload[:-2] + "\n}"
    # base64-encode and remove any trailing =
    jw_payload = base64.urlsafe_b64encode(jw_payload.encode("ascii")).decode("ascii").rstrip("=")
    # add payload as a json attribute, and then add the signatures back
    complete_msg = payload + '   "payload": "{}",\n'.format(jw_payload) + sep + signatures
    _jws = jws.JWS()
    _jws.verify_json(complete_msg.encode("ascii"))


MANIFEST = dict(schemaVersion=2, layers=[dict(digest="sha256:base"), dict(digest="sha256:layer1")])

MANIFEST_WITH_FOREIGN_LAYERS = dict(
    schemaVersion=2,
    layers=[
        dict(
            digest="sha256:base",
            mediaType="application/vnd.docker.image.rootfs.foreign.diff.tar.gzip",
        ),
        dict(digest="sha256:layer1"),
    ],
)

CONFIG_LAYER = dict(
    architecture="amd64",
    author="Mihai Ibanescu <mihai.ibanescu@gmail.com>",
    config=dict(Hostname="decafbad", Cmd=["/bin/bash"]),
    container_config=dict(Hostname="decafbad", Tty=False),
    created="2019-09-05T21:28:52.173079282Z",
    docker_version="1.13.1",
    history=[
        {
            "created": "2018-03-06T00:48:12.077095981Z",
            "created_by": "/bin/sh -c #(nop) ADD file:FILE_CHECKSUM in / ",
        },
        {
            "created": "2018-03-06T00:48:12.458578213Z",
            "created_by": "/bin/sh -c #(nop)  LABEL name=CentOS Base Image vendor=CentOS "
            "license=GPLv2 build-date=20180302",
            "empty_layer": True,
        },
        {
            "created": "2018-03-06T00:48:12.679169547Z",
            "created_by": '/bin/sh -c #(nop)  CMD ["/bin/bash"]',
            "empty_layer": True,
        },
        {
            "created": "2019-09-05T21:28:43.305854958Z",
            "author": "Mihai Ibanescu <mihai.ibanescu@gmail.com>",
            "created_by": "/bin/sh -c #(nop)  MAINTAINER Mihai Ibanescu <mihai.ibanescu@gmail.com>",
            "empty_layer": True,
        },
        {
            "created": "2019-09-05T21:28:46.173079282Z",
            "empty_layer": True,
        },
        {
            "created": "2019-09-05T21:28:52.173079282Z",
            "author": "Mihai Ibanescu <mihai.ibanescu@gmail.com>",
            "created_by": "/bin/sh -c touch /usr/share/dummy.txt",
        },
    ],
    rootfs={
        "type": "layers",
        "diff_ids": ["sha256:uncompressed_base", "sha256:uncompressed_layer1"],
    },
)
