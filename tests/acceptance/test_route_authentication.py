"""
Every route requires a signed in user unless it is listed in PUBLIC_ENDPOINTS.

The routes are read from the application's url map rather than listed here, so
a new route is protected by default: it fails these tests until it either has
@login_required or is added to PUBLIC_ENDPOINTS as a read only page.
"""
import uuid

import pytest
from flask import url_for

from application.factory import create_app

# Read only pages anyone may view. Nothing here may change data.
PUBLIC_ENDPOINTS = {
    "auth.authorize",
    "auth.login",
    "auth.logout",
    "main.change_log",
    "main.csv",
    "main.dataset",
    "main.dataset_json",
    "main.finder",
    "main.history",
    "main.how_we_add_datasets",
    "main.index",
    "main.index_json",
    "main.links",
    "main.schema",
    "main.schema_json",
    "main.support",
    "static",
}

UUID_ARGUMENTS = {"record_id", "update"}


def _routes():
    app = create_app("application.config.TestConfig")
    with app.test_request_context():
        for rule in app.url_map.iter_rules():
            values = {
                argument: str(uuid.uuid4()) if argument in UUID_ARGUMENTS else "example"
                for argument in rule.arguments
            }
            path = url_for(rule.endpoint, **values)
            for method in sorted(rule.methods - {"HEAD", "OPTIONS"}):
                yield rule.endpoint, method, path


ROUTES = list(_routes())


@pytest.mark.parametrize(
    ("endpoint", "method", "path"),
    [route for route in ROUTES if route[0] not in PUBLIC_ENDPOINTS],
)
def test_route_redirects_anonymous_user_to_login(client, endpoint, method, path):
    response = client.open(path, method=method)

    assert response.status_code == 302, f"{method} {path} ({endpoint}) is not protected"
    assert response.headers["Location"].startswith("/auth/login")


@pytest.mark.parametrize(
    ("endpoint", "method", "path"),
    [route for route in ROUTES if route[0] in PUBLIC_ENDPOINTS],
)
def test_public_routes_are_read_only(endpoint, method, path):
    assert method == "GET", f"{method} {path} ({endpoint}) is public but not read only"


def test_public_endpoints_all_exist():
    # stops a renamed or removed endpoint leaving a stale entry in the allow list
    assert PUBLIC_ENDPOINTS <= {endpoint for endpoint, _, _ in ROUTES}
