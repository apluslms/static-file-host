import os
import json

from flask import Flask

from . import config


def create_app(configuration=config.BaseConfig):
    app = Flask(__name__)

    app.config.from_object(configuration)

    manifest_json = os.path.join(app.config.get('STATIC_FILE_PATH'), 'manifest.json')
    if not os.path.exists(manifest_json):
        with open(manifest_json, 'w') as f:
            json.dump({}, f)

    return app










