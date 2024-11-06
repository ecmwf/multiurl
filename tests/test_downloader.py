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

import pytest

from multiurl import Downloader, download
from multiurl.http import FullHTTPDownloader


def test_http():
    Downloader("http://localhost")


def test_ftp():
    Downloader("ftp://localhost")


def test_parts():
    download(
        url="http://get.ecmwf.int/test-data/metview/gallery/temp.bufr",
        target="out.data",
    )

    download(
        url="http://get.ecmwf.int/test-data/metview/gallery/temp.bufr",
        parts=((0, 4),),
        target="out.data",
    )

    assert os.path.getsize("out.data") == 4

    with open("out.data", "rb") as f:
        assert f.read() == b"BUFR"

    download(
        url="http://get.ecmwf.int/test-data/metview/gallery/temp.bufr",
        parts=((0, 10), (50, 10), (60, 10)),
        target="out.data",
    )

    assert os.path.getsize("out.data") == 30

    with open("out.data", "rb") as f:
        assert f.read()[:4] == b"BUFR"


def test_order():
    d = Downloader(
        url="http://get.ecmwf.int/test-data/metview/gallery/temp.bufr",
        parts=((3, 1), (2, 1), (1, 1), (0, 1)),
    )
    d.download(
        target="out.data",
    )

    with open("out.data", "rb") as f:
        assert f.read()[:4] == b"RFUB"

    d = Downloader(
        url="http://get.ecmwf.int/test-data/metview/gallery/temp.bufr",
        parts=reversed([(3, 1), (2, 1), (1, 1), (0, 1)]),
    )
    print(d)
    d.download(
        target="out.data",
    )

    with open("out.data", "rb") as f:
        assert f.read()[:4] == b"BUFR"


def test_content_disposition_handling():
    class TestDownloader(FullHTTPDownloader):
        def headers(self):
            headers = super().headers()
            headers["content-disposition"] = 'attachment; filename="temp.bufr"'
            return headers

    TestDownloader(
        url="http://get.ecmwf.int/test-data/metview/gallery/temp.bufr",
    ).download(target="out")


@pytest.mark.skip(reason="ftpserver not defined")
def test_ftp_download(tmp_path, ftpserver):
    local_test_file = os.path.join(tmp_path, "testfile.txt")
    with open(local_test_file, "w") as f:
        f.write("This is a test file")

    ftp_url = ftpserver.put_files(local_test_file, style="url", anon=True)
    local_test_download = os.path.join(tmp_path, "testdownload.txt")
    download(ftp_url[0], local_test_download)
    with open(local_test_file) as original, open(local_test_download) as downloaded:
        assert original.read() == downloaded.read()

    ftp_url = ftpserver.put_files(local_test_file, style="url", anon=False)
    local_test_download = os.path.join(tmp_path, "testdownload.txt")
    download(ftp_url[0], local_test_download)
    with open(local_test_file) as original, open(local_test_download) as downloaded:
        assert original.read() == downloaded.read()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    # test_order()
