import os
import json
import shutil
import pprint
import logging
import traceback
from uuid import uuid4
import time
from filelock import Timeout, FileLock

from flask import request, jsonify
from werkzeug.exceptions import BadRequest


from management import create_app, config
from management.auth import prepare_decoder, authenticate
from management.utils import (
    compare_files_to_update,
    whether_can_upload,
    upload_octet_stream,
    upload_form_data,
    update_course_dir,
    error_print,
    ImproperlyConfigured,
    file_move_safe,
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


@app.route('/<course_name>/get-files-to-update', methods=['GET', 'POST'])
def get_files_to_update(course_name):
    """
        Get the list of files to update
    """
    auth = authenticate(jwt_decode)

    # the absolute path of the course in the server
    static_file_path = app.config.get('STATIC_FILE_PATH')
    if not static_file_path:
        return ImproperlyConfigured('STATIC_FILE_PATH not configured')

    data = {'course_instance': auth['sub']}

    course_dir = os.path.join(static_file_path, course_name)

    # get the manifest from the client
    try:
        file = request.files['manifest_client'].read()
        manifest_client = json.loads(file.decode('utf-8'))
    except:
        logger.info(traceback.format_exc())
        return BadRequest(error_print())

    # check whether the index html exists in the client side
    index_key = 'index.html'
    if index_key not in manifest_client:
        logger.info("The index html file is not found in the newly built course!")
        return BadRequest("The index html file is not found in the newly built course!")

    # if the course has not been uploaded yet, upload all the files
    if not os.path.exists(course_dir) or not os.path.isdir(course_dir):
        data['exist'] = False
        files_to_update = {'files_new': manifest_client,
                           'files_update': {},
                           'files_keep': {},
                           'files_remove': {}}
    # else if the course already exists
    else:
        with open(os.path.join(static_file_path, course_name, 'manifest.json'), 'r') as manifest_srv_file:
            manifest_srv = json.load(manifest_srv_file)
        # check whether the index mtime is earlier than the one in the server
        # srv_index_mtime = os.stat(os.path.join(course_dir, 'index.html')).st_mtime_ns
        # print(manifest_client[index_key]['mtime'], manifest_srv[index_key]['mtime'], srv_index_mtime)
        if manifest_client[index_key]['mtime'] <= manifest_srv[index_key]['mtime']:
            return BadRequest('Abort: the client version is older than server version')

        data['exist'] = True

        # compare the files between the client side and the server side
        # get list of files to upload / update
        course_manifest_srv = {f: manifest_srv[f] for f in manifest_srv if f.split(os.sep)[0] == course_name}
        files_to_update = compare_files_to_update(manifest_client, course_manifest_srv)

    # get a unique id for this uploading process
    unique_id = str(uuid4())
    data['id'] = unique_id

    # create a temp directory where the files will be uploaded to
    temp_dir = os.path.join(static_file_path, 'temp_' + course_name + '_' + unique_id)
    os.mkdir(temp_dir)
    # Store the files will be updated in a temp json file
    with open(os.path.join(temp_dir, 'files_to_update.json'), 'w') as f:
        # f.write(json.dumps(files_to_update, sort_keys=True, indent=4))
        json.dump(files_to_update, f, sort_keys=True, indent=4)
    data['files_new'], data['files_update'] = files_to_update['files_new'], files_to_update['files_update']

    return jsonify(**data), 200


@app.route('/<course_name>/upload-file', methods=['GET', 'POST'])
def upload_file(course_name):
    """
        Upload/Update static file of a course
    """
    auth = authenticate(jwt_decode)

    # the absolute path of the course in the server
    static_file_path = app.config.get('STATIC_FILE_PATH')
    if not static_file_path:
        return ImproperlyConfigured('STATIC_FILE_PATH not configured')

    # course_directory = os.path.join(static_file_path, course_name)

    status = None  # The status in response
    # check request content-type
    content_type = request.content_type

    # whether_can_upload(content_type, course_directory)

    # upload/ update the courses files of a course
    try:
        if content_type == 'application/octet-stream':

            temp_dir_id = request.headers['ID']
            temp_course_dir = os.path.join(static_file_path, 'temp_' + course_name + '_' + temp_dir_id)

            upload_octet_stream(temp_course_dir)

            if 'Last-File' in request.headers:
                status = "finish"
            else:
                status = "success"

        elif content_type.startswith('multipart/form-data'):

            data, file = request.form, request.files['file']
            temp_dir_id = data['id']
            temp_course_dir = os.path.join(static_file_path, 'temp_' + course_name + '_' + temp_dir_id)
            upload_form_data(file, temp_course_dir)
            if data.get('last_file') is True or data.get('last_file') == 'True':
                status = "finish"
            else:
                status = "success"
        else:
            raise ValueError('Upload-File Error: Unsupported content-type')
    except:
        return BadRequest(error_print())

    return jsonify({
        'course_instance': auth['sub'],
        'status': status
    }), 200


@app.route('/<course_name>/upload-finalizer', methods=['GET'])
def upload_finalizer(course_name):

    auth = authenticate(jwt_decode)
    process_id = request.get_json().get("id")
    if process_id is None:
        return BadRequest("Invalid finalizer of the uploading process")

    # the absolute path of the course in the server
    static_file_path = app.config.get('STATIC_FILE_PATH')
    if not static_file_path:
        return ImproperlyConfigured('STATIC_FILE_PATH not configured')

    temp_course_dir = os.path.join(static_file_path, 'temp_' + course_name + '_' + process_id)
    finalizer_msg = ""

    # if the process failed, remove the temp dir
    if request.get_json().get("upload") != "success":
        if os.path.exists(temp_course_dir):
            shutil.rmtree(temp_course_dir)
        finalizer_msg = "The static files are not uploaded to the server"
        return jsonify({
            'course_instance': auth['sub'],
            'msg': finalizer_msg
        }), 200

    course_dir = os.path.join(static_file_path, course_name)
    manifest_file = os.path.join(static_file_path, course_name, 'manifest.json')

    with open(os.path.join(temp_course_dir, 'files_to_update.json'), 'r') as f:
        files_to_update = json.loads(f.read())

    files_new, files_update, files_keep, files_remove = (files_to_update['files_new'],
                                                         files_to_update['files_update'],
                                                         files_to_update['files_keep'],
                                                         files_to_update['files_remove'])
    if not os.path.exists(course_dir) and(
            not files_update and
            not files_keep and
            not files_remove):
        os.rename(temp_course_dir, course_dir)
        with open(manifest_file, 'w') as f:
            json.dump(files_new, f)
        os.remove(os.path.join(course_dir, 'files_to_update.json'))
    else:
        index_key = "index.html"
        lock_f = os.path.join(static_file_path, course_name+'.lock')
        lock = FileLock(lock_f)
        while True:
            try:
                with lock.acquire(timeout=1):
                    with open(manifest_file, 'r') as f:
                        manifest_srv = json.load(f)

                if request.get_json().get("index_mtime") <= manifest_srv[index_key]['mtime']:
                    raise PermissionError('Abort: the client version is older than server version')

                for f in files_keep:
                    os.link(os.path.join(course_dir, f), os.path.join(temp_course_dir, f))

                # add/update manifest
                files_upload = {**files_new, **files_update}
                for f in files_upload:
                    manifest_srv[f] = files_upload[f]
                # remove old files
                for f in files_remove:
                    # os.remove(os.path.join(course_dir, f.replace(course_name + os.sep, '')))
                    os.remove(os.path.join(course_dir, f))
                    del manifest_srv[f]

                with open(os.path.join(temp_course_dir, 'manifest.json'), 'w') as f:
                    json.dump(manifest_srv, f)

                os.rename(course_dir, course_dir+'_old')
                os.rename(temp_course_dir, course_dir)
                os.remove(os.path.join(course_dir, 'files_to_update.json'))
                shutil.rmtree(course_dir+'_old')
                os.remove(lock_f)
                break
            except Timeout:
                print('another process is running')
                time.sleep(5)
            # if another error raises
            except:
                logger.debug(traceback.format_exc())
                shutil.rmtree(temp_course_dir)
                os.remove(lock_f)
                return BadRequest(traceback.format_exc())

    return jsonify({
        'course_instance': auth['sub'],
        'msg': finalizer_msg
    }), 200


if __name__ == '__main__':
    if os.getenv('FLASK_ENV') == 'development':
        app.run(debug=True, host='0.0.0.0', port=9000)
    else:
        app.run()



