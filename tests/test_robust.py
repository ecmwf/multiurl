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

from multiurl import download
from multiurl.http import RETRIABLE


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
