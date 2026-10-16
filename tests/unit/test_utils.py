import datetime

import pytest

from application.utils import date_to_string, parse_date, url_error


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "  ",
        "https://www.planning.data.gov.uk/",
        "http://example.com/path?query=1#fragment",
        "HTTPS://EXAMPLE.COM",
        "https://example.com:8443/",
        "https://8.8.8.8/",
    ],
)
def test_url_error_accepts_public_http_urls(value):
    assert url_error(value) is None


# includes every url field value seen in the September 2026 attack
@pytest.mark.parametrize(
    "value",
    [
        "file:///etc/passwd",
        "file:///app/application/factory.py",
        "file:///proc/self/environ",
        "gopher://127.0.0.1:80/_GET%20/",
        "http://127.0.0.1/",
        "http://127.0.0.1:1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://169.254.170.2/v2/credentials",
        "http://localhost:5050/",
        "http://app.localhost/",
        "http://[::1]/",
        "http://10.0.0.1/",
        "http://192.168.1.1/",
        "javascript:alert(1)",
        "ftp://example.com/file",
        "example.com",
        "https://",
        "https://exa mple.com/",
        "https://example.com:notaport/",
    ],
)
def test_url_error_rejects_unsafe_urls(value):
    assert url_error(value) is not None


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
