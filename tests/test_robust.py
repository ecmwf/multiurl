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
import random
import threading
from contextlib import contextmanager

import pytest
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


@pytest.mark.parametrize(
    "retry_after,expected_logs",
    [
        [
            0.1,
            [
                ("multiurl.http", 30, "Retrying in 0.1 seconds"),
                ("multiurl.http", 30, "Retrying in 0.1 seconds"),
                ("multiurl.http", 30, "Retrying in 0.1 seconds"),
            ],
        ],
        [
            (0.1, 0.2, 2),
            [
                ("multiurl.http", 30, "Retrying in 0.1 seconds"),
                ("multiurl.http", 30, "Retrying in 0.2 seconds"),
                ("multiurl.http", 30, "Retrying in 0.2 seconds"),
            ],
        ],
    ],
)
def test_robust_incremental_sleep(caplog, retry_after, expected_logs):
    robust_get = robust(requests.get, retry_after=retry_after, maximum_tries=4)
    codes = ",".join(map(str, RETRIABLE))
    robust_get(f"http://httpbin.org/status/{codes}")
    assert caplog.record_tuples[1::2] == expected_logs


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
