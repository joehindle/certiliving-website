import os

from flask import Flask, flash, redirect, url_for, render_template

from .extensions import limiter



def create_app(test_config=None):

    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev',
        DATABASE=os.path.join(app.instance_path, 'flaskr.sqlite'),
        ADMIN_PASSWORD=os.environ.get("ADMIN_PASSWORD", "change-me"),
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

    # ensure the instance folder exists
    os.makedirs(app.instance_path, exist_ok=True)

    from . import db
    db.init_app(app)

    from . import listings
    app.register_blueprint(listings.bp)

    from . import admin
    app.register_blueprint(admin.bp)

    return app