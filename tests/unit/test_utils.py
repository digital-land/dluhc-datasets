import datetime

from application.utils import date_to_string, parse_date


def test_parse_date():
    valid_date_string = "2022-01-01"
    expected_date = datetime.date(2022, 1, 1)
    assert parse_date(valid_date_string) == expected_date

    invalid_date_string = "2022-13-01"
    assert parse_date(invalid_date_string) is None

    empty_date_string = ""
    assert parse_date(empty_date_string) is None

    none_date_string = None
    assert parse_date(none_date_string) is None

    invalid_format_date_string = "01-01-2022"
    assert parse_date(invalid_format_date_string) is None


def test_date_to_string():
    date = datetime.date(2024, 1, 1)
    expected_string = "2024-01-01"
    assert date_to_string(date) == expected_string

    assert date_to_string("") == ""
    assert date_to_string("not a date") == ""
    assert date_to_string(1) == ""
    assert date_to_string(None) == ""
