import os
import logging
import traceback
import shutil
import json
import pprint
import math

from flask import request, jsonify
import jwt
from werkzeug.exceptions import BadRequest, Unauthorized

from static_management import (
    create_app,
    prepare_decoder,
)
from static_management.utils import (
    files_to_update_1,
    whether_can_upload,
    upload_octet_stream,
    upload_form_data,
    update_course_dir,
    error_print,
    ImproperlyConfigured,
)

pp = pprint.PrettyPrinter(indent=4)

logger = logging.getLogger(__name__)

app = create_app()

jwt_decode = prepare_decoder(app)


def jwt_auth():

    if jwt_decode is None:
        raise ImproperlyConfigured(
            "Received request to %s without JWT_PUBLIC_KEY in settings."
            % (__name__,))

    # require authentication header
    if 'Authorization' not in request.headers:
        logger.debug("JWT auth failed: No authorization header")
        raise Unauthorized("No authorization header")
    try:
        scheme, token = request.headers['Authorization'].strip().split(' ', 1)
        if scheme.lower() != 'bearer': raise ValueError()
    except ValueError:
        logger.debug("JWT auth failed: Invalid authorization header: %r",
                     request.headers.get('Authorization', ''))
        raise Unauthorized("Invalid authorization header")

    # decode jwt token
    try:
        return jwt_decode(token)
    except jwt.InvalidTokenError as exc:
        logger.debug("JWT auth failed: %s", exc)
        raise Unauthorized(str(exc))


def authenticate():

    course_name = request.view_args['course_name']
    if not course_name:
        raise Unauthorized('No valid course name provided')

    auth = jwt_auth()

    # check the payload
    if ('sub' not in auth) or (not auth['sub'].strip()):
        return BadRequest("Invalid payload")
    assert auth['sub'].strip() == course_name, 'the course name in the url does not match the jwt token'

    return auth


@app.route('/', methods=['GET'])
def index():
    return "Static File Management Server"


@app.route('/<course_name>/get_files_to_update', methods=['GET', 'POST'])
def get_files_to_update(course_name):
    """
        compare manifest of static files of a course
        between the client side and the server side
    """
    auth = authenticate()

    # the absolute path of the course in the server
    static_file_path = app.config.get('STATIC_FILE_PATH')
    if not static_file_path:
        return ImproperlyConfigured('STATIC_FILE_PATH not configured')

    data = {'course_instance': auth['sub']}

    course_directory = os.path.join(static_file_path, course_name)

    try:
        file = request.files['manifest_client'].read()
        manifest_client = json.loads(file.decode('utf-8'))
        # print(manifest_client)
        # manifest_client = json.load(file)
        # print("manifest of the files in the client side:\n", manifest_client)
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

    # manifest_srv = dict()
    #
    # for basedir, dirs, files in os.walk(course_directory):
    #     for filename in files:
    #         file = os.path.join(basedir, filename)
    #         # manifest = (os.path.getmtime(file), os.path.getsize(file))
    #         manifest = {"mtime": os.path.getmtime(file),
    #                     "size": os.path.getsize(file)}
    #         manifest_srv[os.path.relpath(file, start=course_directory)] = manifest
    # # print(manifest_srv)
    # data['manifest_srv'] = manifest_srv

    # check whether the index html exists in the client side
    index_key = os.path.join(course_name, 'index.html')
    if index_key not in manifest_client:
        logger.info("The index html file is not found in the newly built course!")
        return BadRequest("The index html file is not found in the newly built course!")

    with open(os.path.join(static_file_path, 'manifest.json'), 'r') as manifest_srv_file:
        manifest_srv = json.load(manifest_srv_file)

    # compare the mtime of the index html file
    # print(manifest_client[index_key]['mtime'])
    # print(manifest_srv[index_key]['mtime'])
    # print(math.isclose(float(manifest_client[index_key]['mtime']), float(manifest_srv[index_key]['mtime'])))
    # print(float(manifest_client[index_key]['mtime']) < float(manifest_srv[index_key]['mtime']))

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
    auth = authenticate()

    # the absolute path of the course in the server
    static_file_path = app.config.get('STATIC_FILE_PATH')
    if not static_file_path:
        return ImproperlyConfigured('STATIC_FILE_PATH not configured')

    course_directory = os.path.join(static_file_path, course_name)

    status = None  # The status in response
    # check request content-type
    content_type = request.content_type

    # if not (content_type == 'application/octet-stream' or
    #         content_type.startswith('multipart/form-data')):
    #     logger.warning(content_type)
    #     return BadRequest("Unsupported content-type")

    temp_course_dir = os.path.join(static_file_path, 'temp_' + course_name)

    # check whether the data can be uploaded
    # try:
    #     whether_can_upload(content_type, course_directory, temp_course_dir)
    # except:
    #     return BadRequest(error_print())

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
                    # files_to_update = json.load(f)
                    files_to_update = json.loads(f.read())
                # print("update the course dir, the files_to_update:")
                # print(files_to_update)
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
    app.run(debug=True)
else:
    application = app
