from flask import Flask

from . import config


def create_app(configuration=config.BaseConfig):
    app = Flask(__name__)

    app.config.from_object(configuration)

    return app










