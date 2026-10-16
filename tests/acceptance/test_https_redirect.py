"""
In AWS, TLS ends at CloudFront and requests reach the app over plain http, with
the load balancer setting X-Forwarded-Proto: http. The app must serve those
requests rather than redirect them to https, or health checks fail and visitors
loop. The redirect is only turned on with HTTPS_REDIRECT.
"""
import os
import subprocess
import sys

from application.extensions import db
from application.factory import create_app

PLAIN_HTTP_HEALTH_CHECK = {
    "X-Forwarded-Proto": "http",
    "User-Agent": "ELB-HealthChecker/2.0",
}


def _get_home_page(https_redirect):
    # imported here, after the factory has loaded .flaskenv, as Config reads
    # DATABASE_URL when it is imported
    from application.config import Config

    # the production config, not TestConfig, which runs in debug mode and so
    # would never redirect whatever the setting
    class ProductionConfig(Config):
        SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
        HTTPS_REDIRECT = https_redirect

    app = create_app(ProductionConfig)
    with app.app_context():
        db.create_all()
        return app.test_client().get("/", headers=PLAIN_HTTP_HEALTH_CHECK)


def test_https_redirect_is_off_when_not_set():
    # config is read when the module is imported, so check it in a fresh process
    env = {k: v for k, v in os.environ.items() if k != "HTTPS_REDIRECT"}
    env.setdefault("DATABASE_URL", "sqlite://")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from application.config import Config; print(Config.HTTPS_REDIRECT)",
        ],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == "False"


def test_plain_http_is_served_when_https_redirect_is_off():
    response = _get_home_page(https_redirect=False)

    assert response.status_code == 200


def test_plain_http_is_redirected_when_https_redirect_is_on():
    response = _get_home_page(https_redirect=True)

    assert response.status_code == 302
    assert response.headers["Location"].startswith("https://")
