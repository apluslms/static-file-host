import os
import json
import math
import shutil
import pprint
import logging
import traceback

from flask import request, jsonify
from werkzeug.exceptions import BadRequest


from management import create_app, config
from management.auth import prepare_decoder, authenticate
from management.utils import (
    files_to_update_1,
    whether_can_upload,
    upload_octet_stream,
    upload_form_data,
    update_course_dir,
    error_print,
    ImproperlyConfigured,
)

logger = logging.getLogger(__name__)
pp = pprint.PrettyPrinter(indent=4)


if os.getenv('FLASK_ENV') == 'development':
    app = create_app(config.DevelopmentConfig)
else:
    app = create_app()

jwt_decode = prepare_decoder(app)


@app.route('/', methods=['GET'])
def index():
    return "Static File Management Server"


@app.route('/<course_name>/get_files_to_update', methods=['GET', 'POST'])
def get_files_to_update(course_name):
    """
        compare manifest of static files of a course
        between the client side and the server side
    """
    auth = authenticate(jwt_decode)

    # the absolute path of the course in the server
    static_file_path = app.config.get('STATIC_FILE_PATH')
    if not static_file_path:
        return ImproperlyConfigured('STATIC_FILE_PATH not configured')

    data = {'course_instance': auth['sub']}

    course_directory = os.path.join(static_file_path, course_name)

    try:
        file = request.files['manifest_client'].read()
        manifest_client = json.loads(file.decode('utf-8'))
    except:
        logger.info(traceback.format_exc())
        return BadRequest(error_print())

    if not os.path.exists(course_directory) or not os.path.isdir(course_directory):
        files_to_update = {'files_new': manifest_client,
                           'files_update': {},
                           'files_remove': {}}
        # Store the files will be updated in a temp json file
        with open(os.path.join(static_file_path, course_name + '_files_to_update.json'), 'w') as f:
            # f.write(json.dumps(files_to_update, sort_keys=True, indent=4))
            json.dump(files_to_update, f, sort_keys=True, indent=4)
        data['files_new'], data['files_update'] = files_to_update['files_new'], files_to_update['files_update']
        data['exist'] = False
        return jsonify(**data), 200

    data['exist'] = True

    # check whether the index html exists in the client side
    index_key = os.path.join(course_name, 'index.html')
    if index_key not in manifest_client:
        logger.info("The index html file is not found in the newly built course!")
        return BadRequest("The index html file is not found in the newly built course!")

    with open(os.path.join(static_file_path, 'manifest.json'), 'r') as manifest_srv_file:
        manifest_srv = json.load(manifest_srv_file)

    if (math.isclose(manifest_client[index_key]['mtime'], manifest_srv[index_key]['mtime'])
       or manifest_client[index_key]['mtime'] < manifest_srv[index_key]['mtime']):
        logger.info("The built version is older than the version in the server")
        return BadRequest("The built version is older than the version in the server")

    course_manifest_srv = {f: manifest_srv[f] for f in manifest_srv if f.split(os.sep)[0] == course_name}
    files_to_update = files_to_update_1(manifest_client, course_manifest_srv)
    data['files_new'], data['files_update'] = files_to_update['files_new'], files_to_update['files_update']
    # Store the files will be updated in a temp json file
    with open(os.path.join(static_file_path, course_name+'_files_to_update.json'), 'w') as f:
        json.dump(files_to_update, f, sort_keys=True, indent=4)

    return jsonify(**data), 200


@app.route('/<course_name>/upload', methods=['GET', 'POST'])
def static_upload(course_name):
    """
        Upload/Update static files of a course
    """
    auth = authenticate(jwt_decode)

    # the absolute path of the course in the server
    static_file_path = app.config.get('STATIC_FILE_PATH')
    if not static_file_path:
        return ImproperlyConfigured('STATIC_FILE_PATH not configured')

    course_directory = os.path.join(static_file_path, course_name)

    status = None  # The status in response
    # check request content-type
    content_type = request.content_type

    temp_course_dir = os.path.join(static_file_path, 'temp_' + course_name)

    # upload/ update the courses files of a course
    try:
        if content_type == 'application/octet-stream':

            upload_octet_stream(temp_course_dir)

            if 'Last-File' in request.headers:
                with open(os.path.join(static_file_path, course_name+'_files_to_update.json'), 'r') as f:
                    # files_to_update = json.load(f)
                    files_to_update = json.loads(f.read())
                # print("update the course dir, the files_to_update:")
                # pp.pprint(files_to_update)
                update_course_dir(course_directory, temp_course_dir, files_to_update)
                if os.path.exists(os.path.join(static_file_path, course_name + '_files_to_update.json')):
                    os.remove(os.path.join(static_file_path, course_name + '_files_to_update.json'))
                status = "finish"
            else:
                status = "success"

        elif content_type.startswith('multipart/form-data'):

            data, file = request.form, request.files['file']
            upload_form_data(file, temp_course_dir)
            if data.get('last_file') is True or data.get('last_file') == 'True':
                print("Update the course dir")
                with open(os.path.join(static_file_path, course_name+'_files_to_update.json'), 'r') as f:
                    files_to_update = json.loads(f.read())
                update_course_dir(course_directory, temp_course_dir, files_to_update)
                if os.path.exists(os.path.join(static_file_path, course_name + '_files_to_update.json')):
                    os.remove(os.path.join(static_file_path, course_name + '_files_to_update.json'))
                status = "finish"
            else:
                status = "success"
    except:
        if os.path.exists(temp_course_dir):
            shutil.rmtree(temp_course_dir)
        if os.path.exists(os.path.join(static_file_path, course_name+'_files_to_update.json')):
            os.remove(os.path.join(static_file_path, course_name+'_files_to_update.json'))
        logger.info(traceback.format_exc())
        return BadRequest(error_print())

    return jsonify({
        'course_instance': auth['sub'],
        'status': status
    }), 200


if __name__ == '__main__':
    if os.getenv('FLASK_ENV') == 'development':
        app.run(debug=True, host='0.0.0.0', port=9000)
    else:
        app.run()



