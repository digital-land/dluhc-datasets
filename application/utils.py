# utils.py
import datetime
import json
from functools import wraps


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


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return json.JSONEncoder.default(self, obj)
