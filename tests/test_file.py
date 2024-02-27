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
from contextlib import contextmanager

from multiurl import Downloader, download


@contextmanager
def chdir(path):
    save = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(save)


def test_file():
    Downloader("file://localhost")


def test_absolute_path():
    download(
        __file__,
        target="out.data",
    )


def test_relative_path():
    with chdir(os.path.dirname(__file__)):
        base = os.path.basename(__file__)
        download(base, target="out.data")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    test_absolute_path()
