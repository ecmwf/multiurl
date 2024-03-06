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
        self.urls = []

    def __call__(self, r):
        self.urls.append(r.url)
        return r


def test_auth_single():
    auth = Auth()
    url = "http://get.ecmwf.int/test-data/metview/gallery/temp.bufr"
    download(url=url, target="out.data", auth=auth)

    assert auth.urls == [url]


def test_auth_single_parts():
    auth = Auth()
    url = "http://get.ecmwf.int/test-data/metview/gallery/temp.bufr"

    download(url=url, target="out.data", parts=((0, 4),), auth=auth)

    assert auth.urls == [url]
    assert os.path.getsize("out.data") == 4

    with open("out.data", "rb") as f:
        assert f.read() == b"BUFR"


def test_auth_single_parts():
    auth = Auth()
    url = "http://get.ecmwf.int/test-data/metview/gallery/temp.bufr"

    download(url=url, target="out.data", parts=((0, 4), (20, 4)), auth=auth)

    assert auth.urls == [url]
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

    assert auth.urls == urls
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

    assert auth.urls == urls
    assert os.path.getsize("out.data") == 8

    with open("out.data", "rb") as f:
        assert f.read(4) == b"GRIB"


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    # test_order()
