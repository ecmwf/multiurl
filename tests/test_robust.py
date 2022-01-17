# (C) Copyright 2021 ECMWF.
#
# This software is licensed under the terms of the Apache Licence Version 2.0
# which can be obtained at http://www.apache.org/licenses/LICENSE-2.0.
# In applying this licence, ECMWF does not waive the privileges and immunities
# granted to it by virtue of its status as an intergovernmental organisation
# nor does it submit to any jurisdiction.
#

import logging
import signal
from contextlib import contextmanager

from multiurl import download
from multiurl.http import RETRIABLE


def handler(signum, frame):
    raise TimeoutError()


@contextmanager
def timeout(s):
    save = signal.signal(signal.SIGALRM, handler)
    signal.alarm(s)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, save)


def test_robust():
    sleep = 5
    with timeout(len(RETRIABLE * sleep * 10)):
        for code in RETRIABLE:
            download(
                f"http://httpbin.org/status/200,{code}",
                retry_after=sleep,
                target="test.data",
            )


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
