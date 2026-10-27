# (C) Copyright 2021 ECMWF.
#
# This software is licensed under the terms of the Apache Licence Version 2.0
# which can be obtained at http://www.apache.org/licenses/LICENSE-2.0.
# In applying this licence, ECMWF does not waive the privileges and immunities
# granted to it by virtue of its status as an intergovernmental organisation
# nor does it submit to any jurisdiction.
#

import http.server
import logging
import os
import threading

import pytest

from multiurl import Downloader, download
from multiurl.http import FullHTTPDownloader, PartHTTPDownloader


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


@pytest.mark.parametrize(
    "content_disposition,expected_extension,expected_title",
    [
        ('inline; filename="AND10210000102100001"', ".unknown", "AND10210000102100001"),
        ('inline; filename="data.grib"', ".grib", "data.grib"),
        ('attachment; filename="temp.bufr"', ".bufr", "temp.bufr"),
        ('x-custom; filename="data.nc"', ".nc", "data.nc"),
    ],
)
def test_content_disposition_extension_and_title(
    content_disposition, expected_extension, expected_title
):
    class TestDownloader(FullHTTPDownloader):
        def headers(self):
            return {"content-disposition": content_disposition}

    downloader = TestDownloader(
        url="http://localhost/ecpds/data/file/20261021/AND10210000102100001",
    )
    assert downloader.extension() == expected_extension
    assert downloader.title() == expected_title


INLINE_CONTENT = b"some fixed bytes served with an inline content-disposition"


class InlineHandler(http.server.BaseHTTPRequestHandler):
    def _send_headers(self):
        self.send_response(200)
        self.send_header("Content-Length", str(len(INLINE_CONTENT)))
        self.send_header(
            "Content-Disposition", 'inline; filename="AND10210000102100001"'
        )
        self.end_headers()

    def do_HEAD(self):
        self._send_headers()

    def do_GET(self):
        self._send_headers()
        self.wfile.write(INLINE_CONTENT)

    def log_message(self, format, *args):
        pass


@pytest.fixture
def inline_server():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), InlineHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_inline_content_disposition_local_server(inline_server, tmp_path):
    host, port = inline_server.server_address[:2]
    url = f"http://{host}:{port}/ecpds/data/file/20261021/AND10210000102100001"

    downloader = Downloader(url)
    assert downloader.extension() == ".unknown"

    target = tmp_path / "target"
    downloader.download(str(target))
    assert target.read_bytes() == INLINE_CONTENT


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


class TestPartHTTPDownloader:
    def test_instantiation(self):
        url = "http://localhost"
        downloader = PartHTTPDownloader(url, accept_ranges=True)
        assert downloader.server_capabilities.accept_ranges is True
        assert downloader.server_capabilities.accept_multiple_ranges is True

        downloader = PartHTTPDownloader(url, accept_ranges=False)
        assert downloader.server_capabilities.accept_ranges is False
        assert downloader.server_capabilities.accept_multiple_ranges is False

        downloader = PartHTTPDownloader(
            url, accept_ranges=True, accept_multiple_ranges=False
        )
        assert downloader.server_capabilities.accept_ranges is True
        assert downloader.server_capabilities.accept_multiple_ranges is False

        with pytest.raises(ValueError):
            downloader = PartHTTPDownloader(
                url, accept_ranges=False, accept_multiple_ranges=True
            )

        with pytest.raises(ValueError):
            downloader = PartHTTPDownloader(url, accept_multiple_ranges=False)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    # test_order()
