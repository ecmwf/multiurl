# (C) Copyright 2021 ECMWF.
#
# This software is licensed under the terms of the Apache Licence Version 2.0
# which can be obtained at http://www.apache.org/licenses/LICENSE-2.0.
# In applying this licence, ECMWF does not waive the privileges and immunities
# granted to it by virtue of its status as an intergovernmental organisation
# nor does it submit to any jurisdiction.
#

import datetime
import json
import logging
import os
import random
import time
from dataclasses import dataclass
from typing import Optional

import pytz
import requests
from dateutil.parser import parse as parse_date

from .base import DownloaderBase
from .multipart import DecodeMultipart, PartFilter, compute_byte_ranges
from .retry import robust

LOG = logging.getLogger(__name__)


@dataclass
class ServerCapabilities:
    accept_ranges: bool
    accept_multiple_ranges: bool


def NoFilter(x):
    return x


def parse_separated_header(value: str):
    """Adapted from https://peps.python.org/pep-0594/#cgi."""
    from email.message import Message

    m = Message()
    m["content-type"] = value
    return dict(m.get_params())


class HTTPDownloaderBase(DownloaderBase):
    def __init__(
        self,
        url,
        verify=True,
        http_headers=None,
        fake_headers=None,
        range_method=None,
        maximum_retries=500,
        retry_after=120,
        mirrors=None,
        session=None,
        **kwargs,
    ):
        super().__init__(url, **kwargs)
        self._headers = None
        self._url = None
        self.http_headers = http_headers if http_headers else {}
        self.verify = verify
        self.fake_headers = fake_headers
        self.range_method = range_method
        self.retry_after = retry_after
        self.maximum_retries = maximum_retries
        self.mirrors = mirrors
        self.session = requests if session is None else session

    def headers(self):
        if self._headers is None or self.url != self._url:
            self._url = self.url
            self._headers = {}
            if self.fake_headers is not None:
                self._headers = dict(**self.fake_headers)
            else:
                try:
                    r = self.robust(self.session.head)(
                        self.url,
                        headers=self.http_headers,
                        verify=self.verify,
                        timeout=self.timeout,
                        allow_redirects=True,
                        auth=self.auth,
                    )
                    r.raise_for_status()
                    for k, v in r.headers.items():
                        self._headers[k.lower()] = v
                    LOG.debug(
                        "HTTP headers %s",
                        json.dumps(self._headers, sort_keys=True, indent=4),
                    )
                except Exception:
                    self._url = None
                    self._headers = {}
                    if LOG.level == logging.DEBUG:
                        LOG.exception("HEAD %s", self.url)
                        LOG.error("Ignoring HEAD exception.")
        return self._headers

    def extension(self):
        ext = super().extension()

        if ext == ".unknown":
            # Only check for "content-disposition" if
            # the URL does not end with an extension
            # so we avoid fetching the headers unesseraly

            headers = self.headers()

            if "content-disposition" in headers:
                params = parse_separated_header(headers["content-disposition"])
                assert "attachment" in params, params
                if "filename" in params:
                    ext = super().extension(params["filename"])

        return ext

    def title(self):
        headers = self.headers()
        if "content-disposition" in headers:
            params = parse_separated_header(headers["content-disposition"])
            if "filename" in params:
                return params["filename"]
        return super().title()

    def transfer(self, f, pbar):
        total = 0
        start = time.time()
        stream = self.make_stream()
        for chunk in stream(chunk_size=self.chunk_size):
            self.observer()
            if chunk:
                f.write(chunk)
                total += len(chunk)
                pbar.update(len(chunk))

        self.statistics_gatherer(
            "transfer",
            url=self.url,
            total=total,
            elapsed=time.time() - start,
        )
        return total

    def cache_data(self):
        return self.headers()

    def out_of_date(self, path, cache_data):
        if cache_data is not None:
            # TODO: check 'cache-control' to see if we should check the etag
            if "cache-control" in cache_data:
                pass

            if "expires" in cache_data:
                if cache_data["expires"] != "0":  # HTTP1.0 legacy
                    try:
                        expires = parse_date(cache_data["expires"])
                        now = pytz.UTC.localize(datetime.datetime.utcnow())
                        if expires > now:
                            LOG.debug(
                                "URL %s not expired (%s > %s)", self.url, expires, now
                            )
                            return False
                    except Exception:
                        LOG.exception(
                            "Failed to check URL expiry date '%s'",
                            cache_data["expires"],
                        )

            try:
                headers = self.headers()
            except requests.exceptions.ConnectionError:
                return False

            cached_etag = cache_data.get("etag")
            remote_etag = headers.get("etag")

            if cached_etag != remote_etag and remote_etag is not None:
                LOG.warning("Remote content of URL %s has changed", self.url)
                return True
            else:
                LOG.debug("Remote content of URL %s unchanged", self.url)

        return False

    def check_for_restarts(self, target):
        if not self.resume_transfers:
            return 0

        if not os.path.exists(target):
            return 0

        # Check if we can restarts the transfer
        # TODO: check etags... the file may have changed since

        bytes = os.path.getsize(target)

        if bytes > 0:
            headers = self.headers()
            if headers.get("accept-ranges") != "bytes":
                LOG.warning(
                    "%s: %s bytes already download, but server does not support restarts",
                    target,
                    bytes,
                )
                return 0

            LOG.info(
                "%s: resuming download from byte %s",
                target,
                bytes,
            )

        return bytes

    def issue_request(self, bytes_ranges=None):
        headers = {}
        headers.update(self.http_headers)
        if bytes_ranges is not None:
            headers["range"] = bytes_ranges

        LOG.debug("Issue request for %s", self.url)
        LOG.debug("Headers: %s", json.dumps(headers, indent=4, sort_keys=True))

        r = self.robust(self.session.get)(
            self.url,
            stream=True,
            verify=self.verify,
            timeout=self.timeout,
            headers=headers,
            auth=self.auth,
        )
        try:
            r.raise_for_status()
        except Exception as e:
            if (
                isinstance(e, requests.HTTPError)
                and e.response is not None
                and e.response.status_code == requests.codes.not_found
            ):
                raise  # Keep quiet on 404s
            LOG.error("URL %s: %s", self.url, r.text)
            raise
        return r

    def robust(self, call):
        return robust(call, self.maximum_retries, self.retry_after, self.mirrors)


class FullHTTPDownloader(HTTPDownloaderBase):
    def __repr__(self):
        return f"FullHTTPDownloader({self.url})"

    def estimate_size(self, target):
        assert self.parts is None

        size = None
        mode = "wb"
        skip = 0

        headers = self.headers()
        if "content-length" in headers:
            try:
                size = int(headers["content-length"])
            except Exception:
                LOG.exception("content-length %s", self.url)

        # content-length is the size of the encoded body
        # so we cannot rely on it to check the file size
        trust_size = size is not None and headers.get("content-encoding") is None

        # Check if we can restarts the transfer

        self.range = None
        bytes = self.check_for_restarts(target)
        if bytes > 0:
            assert size is None or bytes < size, (bytes, size, self.url, target)
            skip = bytes
            mode = "ab"
            self.range = f"bytes={bytes}-"

        LOG.debug(
            "url estimate_size size=%s mode=%s skip=%s trust_size=%s",
            size,
            mode,
            skip,
            trust_size,
        )
        return (size, mode, skip, trust_size)

    def make_stream(self):
        request = self.issue_request(self.range)
        return request.iter_content


class ServerDoesNotSupportPartsHTTPDownloader(HTTPDownloaderBase):
    def __repr__(self):
        return f"ServerDoesNotSupportPartsHTTPDownloader({self.url, self.parts})"

    def estimate_size(self, target):
        size = sum(p.length for p in self.parts)
        return (size, "wb", 0, True)

    def make_stream(self):
        request = self.issue_request()
        return PartFilter(self.parts)(request.iter_content)


class SinglePartHTTPDownloader(HTTPDownloaderBase):
    def __repr__(self):
        return f"SinglePartHTTPDownloader({self.url, self.parts})"

    def estimate_size(self, target):
        assert len(self.parts) == 1

        offset, length = self.parts[0]
        start = offset
        end = offset + length - 1
        bytes = self.check_for_restarts(target)
        if bytes > 0:
            start += bytes
            skip = bytes
            mode = "ab"
        else:
            skip = 0
            mode = "wb"

        self.bytes_range = f"bytes={start}-{end}"

        size = sum(p.length for p in self.parts)
        return (size, mode, skip, True)

    def make_stream(self):
        request = self.issue_request(self.bytes_range)
        return request.iter_content


class PartHTTPDownloader(HTTPDownloaderBase):
    def __init__(
        self,
        *args,
        accept_ranges: Optional[bool] = None,
        accept_multiple_ranges: Optional[bool] = None,
        **kwargs,
    ):
        """
        Parameters
        ----------
        *args :
            Positional arguments forwarded to `HTTPDownloaderBase`.
        accept_ranges : bool, optional
            Whether the server supports byte-range requests. If `None`,
            the capability is probed from the response headers at request time.
        accept_multiple_ranges : bool, optional
            Whether the server supports multiple byte ranges in a single
            request. Requires `accept_ranges=True`. If `None` and
            `accept_ranges` is provided, defaults to the same value.
        **kwargs :
            Keyword arguments forwarded to `HTTPDownloaderBase`.

        Raises
        ------
        ValueError
            If `accept_multiple_ranges` is set without `accept_ranges`,
            or if `accept_multiple_ranges=True` while `accept_ranges=False`.
        """
        super().__init__(*args, **kwargs)
        if accept_ranges is None and accept_multiple_ranges is not None:
            raise ValueError(
                "When 'accept_multiple_ranges' is set, 'accept_ranges' must also be set, too."
            )
        if not accept_ranges and accept_multiple_ranges:
            raise ValueError(
                "When 'accept_multiple_ranges' is set to True, 'accept_ranges' must also be True."
            )

        self._server_capabilities = None
        if accept_ranges is not None:
            if accept_multiple_ranges is None:
                accept_multiple_ranges = accept_ranges
            self._server_capabilities = ServerCapabilities(
                accept_ranges=accept_ranges,
                accept_multiple_ranges=accept_multiple_ranges,
            )

    def __repr__(self):
        return f"PartHTTPDownloader({self.url, self.parts})"

    @property
    def server_capabilities(self) -> ServerCapabilities:
        if self._server_capabilities is None:
            self._server_capabilities = ServerCapabilities(
                accept_ranges=False,
                accept_multiple_ranges=False,
            )
            headers = self.headers()
            if headers.get("accept-ranges") == "bytes":
                self._server_capabilities.accept_ranges = True
                self._server_capabilities.accept_multiple_ranges = True

            # Special case for Azure:
            #   The server does not announce byte-range support, but supports it
            #   The server will ignore multiple ranges and return everything
            #   https://docs.microsoft.com/en-us/rest/api/storageservices/specifying-the-range-header-for-blob-service-operations
            # Special case for AWS:
            #   The server will ignore multiple ranges and return everything
            if headers.get("server", "unknown").startswith(
                "Windows-Azure-Blob"
            ) or headers.get("server", "unknown").startswith("AmazonS3"):
                self._server_capabilities.accept_ranges = True
                self._server_capabilities.accept_multiple_ranges = False
        return self._server_capabilities

    def mutate(self, *args, **kwargs):
        if not self.server_capabilities.accept_ranges:
            LOG.warning(
                "Server for %s does not support byte ranges, downloading whole file",
                self.url,
            )
            return ServerDoesNotSupportPartsHTTPDownloader(*args, **kwargs)

        if len(self.parts) == 1:
            # Special case, we let HTTP to its job, so we can resume transfers if needed
            return SinglePartHTTPDownloader(*args, **kwargs)

        return self

    def split_large_requests(self, parts):
        ranges = []
        for offset, length in parts:
            ranges.append(f"{offset}-{offset+length-1}")

        # Nginx default is 4K
        # https://stackoverflow.com/questions/686217/maximum-on-http-header-values
        bytes_range = f"bytes={','.join(ranges)}"

        if len(bytes_range) <= 4000:
            return [(bytes_range, parts)]

        middle = len(parts) // 2
        return self.split_large_requests(parts[:middle]) + self.split_large_requests(
            parts[middle:]
        )

    def estimate_size(self, target):
        size = sum(p.length for p in self.parts)
        return (size, "wb", 0, True)

    def make_stream(self):
        # TODO: implement transfer restarts by trimming the list of parts

        filter = NoFilter
        parts = self.parts

        if self.range_method:
            rounded, positions = compute_byte_ranges(
                self.parts,
                self.range_method,
                self.url,
                self.statistics_gatherer,
            )
            filter = PartFilter(self.parts, positions)
            parts = rounded

        splits = self.split_large_requests(parts)
        accept_multiple_ranges = self.server_capabilities.accept_multiple_ranges

        def iterate_requests(chunk_size):
            for bytes_ranges, parts in splits:
                if accept_multiple_ranges:
                    request = self.issue_request(bytes_ranges)
                else:
                    request = self.issue_request(bytes_ranges.split(",")[0])

                stream = DecodeMultipart(
                    self.url,
                    request,
                    parts,
                    verify=self.verify,
                    timeout=self.timeout,
                    headers=self.http_headers,
                    maximum_retries=self.maximum_retries,
                    retry_after=self.retry_after,
                    mirrors=self.mirrors,
                )

                yield from stream(chunk_size)

        return filter(iterate_requests)
