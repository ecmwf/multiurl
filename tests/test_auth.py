# (C) Copyright 2021 ECMWF.
#
# This software is licensed under the terms of the Apache Licence Version 2.0
# which can be obtained at http://www.apache.org/licenses/LICENSE-2.0.
# In applying this licence, ECMWF does not waive the privileges and immunities
# granted to it by virtue of its status as an intergovernmental organisation
# nor does it submit to any jurisdiction.
#

import logging
import os

from multiurl import download

# NOTE: we just test if the auth object is properly called with the
# requests when using download()


class Auth:
    def __init__(self):
        from collections import defaultdict

        self.calls = defaultdict(set)

    def __call__(self, r):
        method = r.method.lower()
        self.calls[method].add(r.url)
        return r


def test_auth_single():
    auth = Auth()
    url = "http://get.ecmwf.int/test-data/metview/gallery/temp.bufr"
    download(url=url, target="out.data", auth=auth)

    assert auth.calls["head"] == set([url])
    assert auth.calls["get"] == set([url])


def test_auth_single_fake_headers():
    auth = Auth()
    url = "http://get.ecmwf.int/test-data/metview/gallery/temp.bufr"
    download(url=url, target="out.data", auth=auth, fake_headers={})

    assert auth.calls["head"] == set()
    assert auth.calls["get"] == set([url])


def test_auth_single_parts():
    auth = Auth()
    url = "http://get.ecmwf.int/test-data/metview/gallery/temp.bufr"

    download(url=url, target="out.data", parts=((0, 4),), auth=auth)

    assert auth.calls["head"] == set([url])
    assert auth.calls["get"] == set([url])
    assert os.path.getsize("out.data") == 4

    with open("out.data", "rb") as f:
        assert f.read() == b"BUFR"


def test_auth_single_multi_parts():
    auth = Auth()
    url = "http://get.ecmwf.int/test-data/metview/gallery/temp.bufr"

    download(url=url, target="out.data", parts=((0, 4), (20, 4)), auth=auth)

    assert auth.calls["head"] == set([url])
    assert auth.calls["get"] == set([url])
    assert os.path.getsize("out.data") == 8

    with open("out.data", "rb") as f:
        assert f.read(4) == b"BUFR"


def test_auth_multi():
    auth = Auth()
    urls = [
        "http://get.ecmwf.int/test-data/earthkit-data/examples/test.grib",
        "http://get.ecmwf.int/test-data/earthkit-data/examples/test6.grib",
    ]

    download(url=urls, target="out.data", auth=auth)

    assert auth.calls["head"] == set(urls)
    assert auth.calls["get"] == set(urls)
    assert os.path.getsize("out.data") == 2492

    with open("out.data", "rb") as f:
        assert f.read(4) == b"GRIB"


def test_auth_multi_parts():
    auth = Auth()
    urls = [
        "http://get.ecmwf.int/test-data/earthkit-data/examples/test.grib",
        "http://get.ecmwf.int/test-data/earthkit-data/examples/test6.grib",
    ]

    download(url=urls, target="out.data", parts=((0, 4),), auth=auth)

    assert auth.calls["head"] == set(urls)
    assert auth.calls["get"] == set(urls)
    assert os.path.getsize("out.data") == 8

    with open("out.data", "rb") as f:
        assert f.read(4) == b"GRIB"
        assert f.read(4) == b"GRIB"


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    # test_order()
