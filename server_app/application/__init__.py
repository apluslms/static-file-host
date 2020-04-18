import threading
from flask import Flask

from apluslms_file_transfer.server.action_general import start_cleanup
from apluslms_file_transfer.exceptions import ImproperlyConfigured

from . import config

CLEANUP_TIME = 60*60*24  # a day
# CLEANUP_TIME = 60  # 1 minute, for development purpose
cleanup_thread = threading.Thread(daemon=True)


def create_app(configuration=config.BaseConfig):
    app = Flask(__name__)
    app.config.from_object(configuration)

    # the absolute path of the course in the server
    upload_dir = app.config.get('UPLOAD_DIR')
    if upload_dir is None:
        return ImproperlyConfigured('UPLOAD_DIR not configured')

    start_cleanup(upload_dir, CLEANUP_TIME)

    return app










