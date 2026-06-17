from multiurl.http import RETRIABLE


def test_retriable_is_list_or_tuple():
    assert isinstance(RETRIABLE, (list, tuple))
