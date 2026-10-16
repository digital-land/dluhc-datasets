# -*- coding: utf-8 -*-
import os

from flask import Flask
from flask.cli import load_dotenv

from application.models import *  # noqa

load_dotenv()


def create_app(config_filename):
    app = Flask(__name__)
    app.config.from_object(config_filename)
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 10

    register_blueprints(app)
    register_context_processors(app)
    register_templates(app)
    register_filters(app)
    register_extensions(app)
    register_error_handlers(app)
    register_commands(app)

    return app


def register_blueprints(app):
    from application.blueprints.auth.views import auth
    from application.blueprints.main.views import main
    from application.blueprints.uploads.views import upload

    app.register_blueprint(main)
    app.register_blueprint(auth)
    app.register_blueprint(upload)


def register_context_processors(app):
    """
    Add template context variables and functions
    """

    def base_context_processor():
        return {"assetPath": "/static"}

    app.context_processor(base_context_processor)


def register_filters(app):
    from application.filters import value_or_empty_string

    app.add_template_filter(value_or_empty_string)


def register_extensions(app):
    from application.extensions import csrf, db, migrate, oauth

    db.init_app(app)
    migrate.init_app(app, db)
    oauth.init_app(app)
    # every POST must carry a CSRF token, including routes that read
    # request.form directly rather than through a FlaskForm
    csrf.init_app(app)

    # Only for hosting where TLS ends at the app itself. Behind CloudFront, which
    # redirects http visitors itself and reaches the app over plain http, the app
    # cannot tell an https visitor from an http one and redirecting would loop.
    if app.config["HTTPS_REDIRECT"]:
        from flask_sslify import SSLify

        SSLify(app)

    # create the CSP for the app - until then leave commented out
    # talisman.init_app(app, content_security_policy=None)

    oauth.register(
        name="github",
        client_id=app.config["GITHUB_CLIENT_ID"],
        client_secret=app.config["GITHUB_CLIENT_SECRET"],
        access_token_url="https://github.com/login/oauth/access_token",
        access_token_params=None,
        authorize_url="https://github.com/login/oauth/authorize",
        authorize_params=None,
        api_base_url="https://api.github.com/",
        client_kwargs={"scope": "user:email read:org"},
    )

    if os.environ.get("SENTRY_DSN") is not None:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration

        sentry_sdk.init(
            dsn=os.environ.get("SENTRY_DSN"), integrations=[FlaskIntegration()]
        )


def register_error_handlers(app):
    from flask import render_template, request, url_for
    from flask_wtf.csrf import CSRFError
    from is_safe_url import is_safe_url

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        # usually a form left open longer than WTF_CSRF_TIME_LIMIT
        back_url = request.referrer
        if not back_url or not is_safe_url(back_url, app.config.get("SAFE_URLS", {})):
            back_url = url_for("main.index")
        return render_template("session-expired.html", back_url=back_url), 400


def register_templates(app):
    """
    Register templates from packages
    """
    from jinja2 import ChoiceLoader, PackageLoader, PrefixLoader

    multi_loader = ChoiceLoader(
        [
            app.jinja_loader,
            PrefixLoader(
                {
                    "govuk_frontend_jinja": PackageLoader("govuk_frontend_jinja"),
                    "digital-land-frontend": PackageLoader("digital_land_frontend"),
                    "govuk_frontend_wtf": PackageLoader("govuk_frontend_wtf"),
                }
            ),
        ]
    )
    app.jinja_loader = multi_loader


def register_commands(app):
    from application.commands import data_cli

    app.cli.add_command(data_cli)
