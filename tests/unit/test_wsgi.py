import importlib


def test_wsgi_app_defaults_to_production_config(monkeypatch):
    monkeypatch.delenv("FLASK_CONFIG", raising=False)

    import application.wsgi

    app = importlib.reload(application.wsgi).app

    assert app.config["AUTHENTICATION_ON"] is True
    assert app.config["DEBUG"] is False
    assert app.config.get("WTF_CSRF_ENABLED", True) is True
