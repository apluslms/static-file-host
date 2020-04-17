import os
import json
import pprint
import logging

from flask import request, jsonify
from werkzeug.exceptions import BadRequest

from apluslms_file_transfer.server.action_general import files_to_update, publish_files
from apluslms_file_transfer.server.auth import prepare_decoder, authenticate
from apluslms_file_transfer.server.flask import upload_files
from apluslms_file_transfer.server.utils import tempdir_path
from apluslms_file_transfer.exceptions import ImproperlyConfigured

from application import create_app, config


os.environ['SERVER_FILE'] = 'html'
logger = logging.getLogger(__name__)
pp = pprint.PrettyPrinter(indent=4)

if os.getenv('FLASK_ENV') == 'development':
    app = create_app(config.DevelopmentConfig)
else:
    app = create_app()

jwt_decode = prepare_decoder(app)

if jwt_decode is None:
    raise ImproperlyConfigured(
        "Received request to %s without JWT_PUBLIC_KEY in settings."
        % (__name__,))


@app.route('/', methods=['GET'])
def index():
    return "Static File Management Server"


@app.route('/<course_name>/get-files-to-update', methods=['GET', 'POST'])
def get_files_to_update(course_name):
    """
        Get the list of files to update
    """
    auth = authenticate(jwt_decode, request.headers, course_name)

    try:
        # get the manifest from the client
        file = request.files['manifest_client'].read()
        manifest_client = json.loads(file.decode('utf-8'))

        res_data = {'course_instance': auth['sub']}  # init the response data
        res_data = files_to_update(app.config.get('UPLOAD_DIR'), course_name, manifest_client, res_data)
    except Exception as e:
        logger.info(e)
        return BadRequest(str(e))

    return jsonify(**res_data), 200


@app.route('/<course_name>/upload-file', methods=['GET', 'POST'])
def upload_file(course_name):
    """
        Upload/Update static file of a course
    """
    auth = authenticate(jwt_decode, request.headers, course_name)

    res_data = {'course_instance': auth['sub']}
    try:
        res_data = upload_files(app.config.get('UPLOAD_DIR'), course_name, res_data)
    except Exception as e:
        return BadRequest(e)

    return jsonify(**res_data), 200


@app.route('/<course_name>/upload-finalizer', methods=['GET'])
def upload_finalizer(course_name):

    auth = authenticate(jwt_decode, request.headers, course_name)

    process_id = request.get_json().get("process_id")
    if process_id is None:
        return BadRequest("Invalid finalizer of the uploading process")

    temp_course_dir = tempdir_path(app.config.get('UPLOAD_DIR'), course_name, process_id)
    if not os.path.exists(os.path.join(temp_course_dir, 'manifest.json')):  # the uploading is not completed
        return BadRequest("The upload is not completed")

    res_data = {'course_instance': auth['sub']}

    res_data = publish_files(upload_dir=app.config.get('UPLOAD_DIR'),
                             course_name=course_name,
                             file_type=os.environ['SERVER_FILE'],
                             temp_course_dir=temp_course_dir,
                             res_data=res_data)

    return jsonify(**res_data), 200


if __name__ == '__main__':
    if os.getenv('FLASK_ENV') == 'development':
        app.run(debug=True, host='0.0.0.0', port=5000)
    else:
        app.run()



