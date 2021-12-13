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

from multiurl import Downloader, download


def test_http():
    Downloader("http://localhost")


def test_ftp():
    Downloader("ftp://localhost")


def test_file():
    Downloader("file://localhost")


def test_absolute_path():
    Downloader(__file__)


def test_relative_path():
    base = os.path.basename(__file__)
    path = os.path.join("..", base)
    Downloader(path)


def test_parts():

    download(
        url="http://download.ecmwf.int/test-data/metview/gallery/temp.bufr",
        target="out.data",
    )

    download(
        url="http://download.ecmwf.int/test-data/metview/gallery/temp.bufr",
        parts=((0, 4),),
        target="out.data",
    )

    assert os.path.getsize("out.data") == 4

    with open("out.data", "rb") as f:
        assert f.read() == b"BUFR"

    download(
        url="http://download.ecmwf.int/test-data/metview/gallery/temp.bufr",
        parts=((0, 10), (50, 10), (60, 10)),
        target="out.data",
    )

    assert os.path.getsize("out.data") == 30

    with open("out.data", "rb") as f:
        assert f.read()[:4] == b"BUFR"


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    test_parts()
