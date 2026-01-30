import pytest


@pytest.fixture
def app():
    from application.factory import create_app

    app = create_app("application.config.TestConfig")

    # If CSRF is enabled in TestConfig, route POST tests will fail without tokens.
    # Safe to disable for tests unless you explicitly want to test CSRF behaviour.
    app.config["WTF_CSRF_ENABLED"] = False

    yield app


@pytest.fixture
def client(app):
    return app.test_client()

from application.extensions import db

@pytest.fixture(autouse=True)
def db_session(app):
    with app.app_context():
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()
