# (C) Copyright 2021 ECMWF.
#
# This software is licensed under the terms of the Apache Licence Version 2.0
# which can be obtained at http://www.apache.org/licenses/LICENSE-2.0.
# In applying this licence, ECMWF does not waive the privileges and immunities
# granted to it by virtue of its status as an intergovernmental organisation
# nor does it submit to any jurisdiction.
#

import datetime
import logging
import os
import random
import threading
from contextlib import contextmanager

import pytest
import pytz
import requests

from multiurl import download
from multiurl.http import RETRIABLE, robust


def handler(signum, frame):
    raise TimeoutError()


@contextmanager
def timeout(s):
    def killer():
        os._exit(1)

    save = threading.Timer(s, killer)
    save.start()
    try:
        yield
    finally:
        save.cancel()


def test_robust():
    sleep = 5
    with timeout(len(RETRIABLE * sleep * 10)):
        code = random.choice(RETRIABLE)
        download(
            f"http://httpbin.org/status/200,{code}",
            retry_after=sleep,
            target="test.data",
        )


def test_retry_header():
    # patch requests.get to add a Retry-After header
    def patched_get(retry, *args, **kwargs):
        r = requests.get(*args, **kwargs)
        if callable(retry):
            retry = retry()
        r.headers.update({"Retry-After": retry})
        return r

    def http_date():
        gmt = pytz.timezone("GMT")
        now = datetime.datetime.now(gmt)
        return (now + datetime.timedelta(seconds=10)).strftime(
            "%a, %d %b %Y %H:%M:%S GMT"
        )

    # test with seconds and http date format
    for retry in ["5", http_date]:
        with timeout(60):
            code = random.choice(RETRIABLE)
            r = robust(
                patched_get, maximum_tries=2, retry_after=120, respect_retry_header=True
            )(retry, f"http://httpbin.org/status/{code}")
            assert r.status_code == code


@pytest.mark.skipif(True, reason="Mirror disabled")
def test_mirror():
    download(
        "http://datastore.copernicus-climate.eu/error/test-data/metview/gallery/temp.bufr",
        mirrors={
            "http://datastore.copernicus-climate.eu/error/": [
                "http://download.ecmwf.int/"
            ]
        },
        target="data.bufr",
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    test_mirror()
