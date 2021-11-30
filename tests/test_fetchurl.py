from multiurl import Downloader


def test_http():
    Downloader("http://localhost")


def test_ftp():
    Downloader("ftp://localhost")


def test_file():
    Downloader("file://localhost")
