import os
import secrets

from flask import Flask, abort, render_template, request, session
from dotenv import load_dotenv

from .extensions import limiter



def create_app(test_config=None):
    load_dotenv()

    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        DATABASE_URL=os.environ.get("DATABASE_URL"),
        SECRET_KEY=os.environ.get("SECRET_KEY"),
        ADMIN_PASSWORD=os.environ.get("ADMIN_PASSWORD"),
        RESEND_API_KEY=os.environ.get("RESEND_API_KEY"),
        RESEND_FROM_EMAIL=os.environ.get("RESEND_FROM_EMAIL", "onboarding@resend.dev"),
        ENQUIRY_TO_EMAIL=os.environ.get("ENQUIRY_TO_EMAIL", "team@certiliving.co.uk"),
        TURNSTILE_SITE_KEY=os.environ.get("TURNSTILE_SITE_KEY"),
        TURNSTILE_SECRET_KEY=os.environ.get("TURNSTILE_SECRET_KEY"),
        R2_ACCOUNT_ID=os.environ.get("R2_ACCOUNT_ID"),
        R2_ACCESS_KEY_ID=os.environ.get("R2_ACCESS_KEY_ID"),
        R2_SECRET_ACCESS_KEY=os.environ.get("R2_SECRET_ACCESS_KEY"),
        R2_BUCKET=os.environ.get("R2_BUCKET"),
        R2_PUBLIC_BASE_URL=os.environ.get("R2_PUBLIC_BASE_URL"),
    )

    limiter.init_app(app)

    @app.errorhandler(429)
    def ratelimit_handler(e):
        return render_template("429.html"), 429

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY is required. Set it via env or instance/config.py.")
    if not app.config.get("ADMIN_PASSWORD"):
        raise RuntimeError("ADMIN_PASSWORD is required. Set it via env or instance/config.py.")
    if not app.config.get("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required. Set it via env or instance/config.py.")

    @app.context_processor
    def inject_csrf_token():
        token = session.get("_csrf_token")
        if token is None:
            token = secrets.token_urlsafe(32)
            session["_csrf_token"] = token
        turnstile_site_key = app.config.get("TURNSTILE_SITE_KEY")
        turnstile_secret_key = app.config.get("TURNSTILE_SECRET_KEY")
        return {
            "csrf_token": token,
            "turnstile_site_key": turnstile_site_key,
            "turnstile_enabled": bool(turnstile_site_key and turnstile_secret_key),
        }

    @app.before_request
    def csrf_protect():
        if app.testing:
            return
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            token = request.form.get("csrf_token") or request.headers.get("X-CSRFToken")
            if not token or token != session.get("_csrf_token"):
                abort(400)

    # ensure the instance folder exists
    os.makedirs(app.instance_path, exist_ok=True)

    from . import db
    db.init_app(app)

    from . import listings
    app.register_blueprint(listings.bp)

    from . import admin
    app.register_blueprint(admin.bp)

    return app
