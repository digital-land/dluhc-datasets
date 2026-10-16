# utils.py
import datetime
import ipaddress
import json
from functools import wraps
from urllib.parse import urlsplit

ALLOWED_URL_SCHEMES = {"http", "https"}


def is_url_field(field):
    return field.datatype == "url" or "url" in field.field


def url_error(value):
    """
    Return why value is not acceptable for a url field, or None if it is.

    Only http and https links to a public host are accepted. Anything else, such
    as file:// or a link to a local or internal address, has no place in a
    published dataset and is a way to probe whatever later fetches the link.
    An empty value is accepted, as url fields are optional.
    """
    if value is None or str(value).strip() == "":
        return None

    try:
        parts = urlsplit(str(value).strip())
        hostname = parts.hostname
        parts.port  # raises ValueError for a port that is not a number
    except ValueError:
        return "is not a valid url"

    if parts.scheme.lower() not in ALLOWED_URL_SCHEMES:
        return "must start with http:// or https://"
    if not hostname or any(character.isspace() for character in parts.netloc):
        return "must include a website address after http:// or https://"
    if hostname == "localhost" or hostname.endswith(".localhost"):
        return "must not link to a local or internal address"
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return None
    if not address.is_global:
        return "must not link to a local or internal address"
    return None


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import current_app, redirect, request, session, url_for

        if current_app.config.get("AUTHENTICATION_ON", True):
            if session.get("user") is None:
                return redirect(url_for("auth.login", next=request.url))
        return f(*args, **kwargs)

    return decorated_function


def parse_date(date_string):
    if date_string is None:
        return None
    if isinstance(date_string, datetime.date):
        return date_string
    try:
        date_object = datetime.datetime.strptime(date_string, "%Y-%m-%d").date()
        return date_object
    except ValueError:
        print(
            f"Could not parse date {date_string} - try with year only and default to 1st Jan"
        )

    try:
        date_object = (
            datetime.datetime.strptime(date_string, "%Y").date().replace(month=1, day=1)
        )
        return date_object

    except ValueError:
        print(f"Could not parse date {date_string} - skip processing")
        return None


def date_to_string(date):
    try:
        return date.strftime("%Y-%m-%d")
    except Exception:
        return ""


def collect_start_date(data):
    parts = []
    format = ""
    if data.get("start-date-year"):
        parts.append(data.get("start-date-year"))
        format = "%Y"
    if data.get("start-date-month"):
        parts.append(data.get("start-date-month"))
        format = f"{format}-%m"
    if data.get("start-date-day"):
        parts.append(data.get("start-date-day"))
        format = f"{format}-%d"
    if parts:
        return "-".join(parts), format
    else:
        return None, None


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return json.JSONEncoder.default(self, obj)
