from multiurl import get_downloader


def test_http():
    get_downloader("http://localhost")


def test_ftp():
    get_downloader("ftp://localhost")


def test_file():
    get_downloader("file://localhost")
