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
from pathlib import Path
from urllib.parse import urlparse

from .file import FullFileDownloader, PartFileDownloader
from .ftp import FullFTPDownloader, PartFTPDownloader
from .heuristics import Part
from .http import FullHTTPDownloader, PartHTTPDownloader, robust
from .multipart import compress_parts

LOG = logging.getLogger(__name__)

__all__ = ["Downloader", "download", "robust"]

DOWNLOADERS = {
    ("ftp", False): FullFTPDownloader,
    ("ftp", True): PartFTPDownloader,
    ("http", False): FullHTTPDownloader,
    ("http", True): PartHTTPDownloader,
    ("https", False): FullHTTPDownloader,
    ("https", True): PartHTTPDownloader,
    ("file", False): FullFileDownloader,
    ("file", True): PartFileDownloader,
}


def Downloader(url, **kwargs):

    if isinstance(url, (list, tuple)):
        from .multiurl import MultiDownloader

        assert len(url) > 0
        downloaders = []
        if isinstance(url[0], (list, tuple)):
            assert "parts" not in kwargs
            for u, p in url:
                downloaders.append(Downloader(u, parts=p, **kwargs))
        else:
            p = kwargs.pop("parts", None)
            for u in url:
                downloaders.append(Downloader(u, parts=p, **kwargs))

        if len(downloaders) == 1:
            return downloaders[0]

        return MultiDownloader(downloaders)

    parts = kwargs.get("parts")
    if parts is not None:
        parts = [Part(offset, length) for offset, length in parts]
        parts = compress_parts(parts)
        if len(parts) == 0:
            parts = None
        kwargs["parts"] = parts

    o = urlparse(url)
    has_parts = parts is not None and len(parts) > 0

    downloader = DOWNLOADERS.get((o.scheme, has_parts))
    if downloader is None:
        path = Path(url)
        if not path.is_absolute():
            path = Path(os.path.abspath(path))
        url = path.as_uri()
        o = urlparse(url)
        downloader = DOWNLOADERS[(o.scheme, has_parts)]

    return downloader(url, **kwargs)


def download(url, target, **kwargs):
    return Downloader(url, **kwargs).download(target)
