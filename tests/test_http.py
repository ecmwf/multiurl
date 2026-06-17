from multiurl.http import RETRIABLE


def test_retriable_is_list_of_strings():
    assert isinstance(RETRIABLE, list)
    assert all(isinstance(item, str) for item in RETRIABLE)

