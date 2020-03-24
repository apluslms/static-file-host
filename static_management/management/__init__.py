import os
import shutil
import threading
from flask import Flask

from . import config

CLEANUP_TIME = 60*60*24*7  # a week


def create_app(configuration=config.BaseConfig):
    app = Flask(__name__)

    app.config.from_object(configuration)

    def cleanup():
        # global cleanup_thread
        static_path = app.config.get('STATIC_FILE_PATH')
        dirs = next(os.walk(static_path))[1]
        for temp_dir in [d for d in dirs if d.startswith('temp')]:
            shutil.rmtree(os.path.join(static_path, temp_dir))

        # Set the next thread to happen
        cleanup_thread = threading.Timer(CLEANUP_TIME, cleanup)
        cleanup_thread.daemon = True
        cleanup_thread.start()

    def cleanup_start():
        # Do initialisation stuff here
        # global cleanup_thread
        # Create your thread
        cleanup_thread = threading.Timer(CLEANUP_TIME, cleanup)
        cleanup_thread.daemon = True
        cleanup_thread.start()

    cleanup_start()

    # with app.app_context():
    #     while True:
    #         time.sleep(CLEANUP_TIME)
    #         static_path = app.config.get('STATIC_FILE_PATH')
    #         dirs = next(os.walk(static_path))[1]
    #         for temp_dir in [d for d in dirs if d.startswith('temp')]:
    #             shutil.rmtree(os.path.join(static_path, temp_dir))

    return app










