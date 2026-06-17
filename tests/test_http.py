from multiurl.http import RETRIABLE


def test_retriable_is_list_of_strings():
    assert isinstance(RETRIABLE, (list, tuple))

