import os

# 3rd party libs
from flask import Flask, request, session, redirect, flash

# from this project
from static_management import config

__version__ = '0.1'

config = {
    "development": "static_management.config.DevelopmentConfig",
    "testing": "static_management.config.TestingConfig",
    "default": "static_management.config.DevelopmentConfig"
}


def configure_app(app):
    config_name = os.getenv('FLASK_CONFIGURATION', 'default')
    app.config.from_object(config[config_name])  # object-based default configuration
    # app.config.from_pyfile('config.py', silent=True)  # instance-folders configuration


def create_app():

    app = Flask(__name__, instance_relative_config=True)
    configure_app(app)
    app.jinja_env.add_extension('jinja2.ext.loopcontrols')

    with app.app_context():

        from static_management.views import bp
        app.register_blueprint(bp)

        # Handle HTTP 403 error
        @app.errorhandler(403)
        def access_forbidden(e):
            session['redirected_from'] = request.url
            flash('Access Forbidden')
            return redirect('/')

    return app
