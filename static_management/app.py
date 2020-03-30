import os
import json
import shutil
import pprint
import logging
import traceback
from uuid import uuid4
from filelock import FileLock

from flask import request, jsonify
from werkzeug.exceptions import BadRequest


from management import create_app, config
from management.auth import prepare_decoder, authenticate
from management.utils import (
    compare_files_to_update,
    upload_octet_stream,
    upload_form_data,
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

    # get the manifest from the client
    try:
        file = request.files['manifest_client'].read()
        manifest_client = json.loads(file.decode('utf-8'))
    except:
        logger.info(traceback.format_exc())
        return BadRequest(error_print())

    # check whether the index file exists in the client side
    index_key = "index.{}".format(os.environ.get('FILE_TYPE'))
    if index_key not in manifest_client:
        logger.info("The {} is not found in the newly built course!".format(index_key))
        return BadRequest("The {} is not found in the newly built course!".format(index_key))

    course_dir = os.path.join(static_file_path, course_name)
    data = {'course_instance': auth['sub']}  # init the response data

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
        if manifest_client[index_key]['mtime'] <= manifest_srv[index_key]['mtime']:
            return BadRequest('Abort: the client version is older than server version')
        data['exist'] = True  # indicate the course exists in the server

        # compare the files between the client side and the server side
        # get list of files to upload / update
        course_manifest_srv = {f: manifest_srv[f] for f in manifest_srv if f.split(os.sep)[0] == course_name}
        files_to_update = compare_files_to_update(manifest_client, course_manifest_srv)

    # get a unique id for this uploading process
    process_id = str(uuid4())
    data['process_id'] = process_id

    # create a temp directory where the files will be uploaded to
    temp_dir = os.path.join(static_file_path, 'temp_' + course_name + '_' + process_id)
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

    content_type = request.content_type

    # upload/ update the courses files of a course
    try:
        if content_type == 'application/octet-stream':

            process_id = request.headers['Process-ID']
            index_mtime = int(request.headers['Index-Mtime'])
            temp_course_dir = os.path.join(static_file_path, 'temp_' + course_name + '_' + process_id)

            upload_octet_stream(temp_course_dir)

            if 'Last-File' in request.headers:
                status = "completed"
            else:
                status = "in process - success"

        elif content_type.startswith('multipart/form-data'):

            data, file = request.form, request.files['file']
            process_id = data['process_id']
            index_mtime = int(data['index_mtime'])
            temp_course_dir = os.path.join(static_file_path, 'temp_' + course_name + '_' + process_id)
            upload_form_data(file, temp_course_dir)
            if data.get('last_file') is True or data.get('last_file') == 'True':
                status = "completed"
            else:
                status = "in process - success"
        else:
            raise ValueError('Upload-File Error: Unsupported content-type')
    except:
        return BadRequest(error_print())

    # The previous implementation create new manifest in the upload-finalizer endpoint
    # now move this step in the upload-file endpoint
    # if the manifest.json in the temp dir, it could be said that the upload is completed?
    # Or if any problems occurs, rename the folder as 'fail_*' to indicate it is a dropped temp dir?
    with open(os.path.join(temp_course_dir, 'files_to_update.json'), 'r') as f:
        files_to_update = json.loads(f.read())

    files_new, files_update, files_keep, files_remove = (files_to_update['files_new'],
                                                         files_to_update['files_update'],
                                                         files_to_update['files_keep'],
                                                         files_to_update['files_remove'])
    os.remove(os.path.join(temp_course_dir, 'files_to_update.json'))

    course_dir = os.path.join(static_file_path, course_name)

    if not os.path.exists(course_dir) and not files_update and not files_keep and not files_remove:
        with open(os.path.join(temp_course_dir, 'manifest.json'), 'w') as f:
            json.dump(files_new, f)
    else:
        index_key = "index.{}".format(os.environ.get('FILE_TYPE'))
        manifest_file = os.path.join(static_file_path, course_name, 'manifest.json')
        lock_f = os.path.join(static_file_path, course_name + '.lock')
        lock = FileLock(lock_f)
        try:
            with lock.acquire(timeout=1):
                with open(manifest_file, 'r') as f:
                    manifest_srv = json.load(f)

            if index_mtime <= manifest_srv[index_key]['mtime']:
                raise PermissionError('Abort: the client version is older than server version')

            for f in files_keep:
                os.link(os.path.join(course_dir, f), os.path.join(temp_course_dir, f))

            # add/update manifest
            files_upload = {**files_new, **files_update}
            for f in files_upload:
                manifest_srv[f] = files_upload[f]
            # remove old files
            for f in files_remove:
                # os.remove(os.path.join(course_dir, f))
                del manifest_srv[f]

            with open(os.path.join(temp_course_dir, 'manifest.json'), 'w') as f:
                json.dump(manifest_srv, f)
            os.remove(lock_f)
        except:
            logger.debug(traceback.format_exc())
            os.remove(lock_f)
            return BadRequest(traceback.format_exc())

    return jsonify({
        'course_instance': auth['sub'],
        'status': status
    }), 200


@app.route('/<course_name>/upload-finalizer', methods=['GET'])
def upload_finalizer(course_name):

    auth = authenticate(jwt_decode)
    process_id = request.get_json().get("process_id")
    if process_id is None:
        return BadRequest("Invalid finalizer of the uploading process")

    # the absolute path of the course in the server
    static_file_path = app.config.get('STATIC_FILE_PATH')
    if not static_file_path:
        return ImproperlyConfigured('STATIC_FILE_PATH not configured')

    temp_course_dir = os.path.join(static_file_path, 'temp_' + course_name + '_' + process_id)
    if not os.path.exists(os.path.join(temp_course_dir, 'manifest.json')):  # The uploading is not completed
        return BadRequest("The upload is not completed")

    course_dir = os.path.join(static_file_path, course_name)

    # if the course does exist, rename the temp dir
    if not os.path.exists(course_dir):
        os.rename(temp_course_dir, course_dir)
    # if the course already exist
    else:
        manifest_file = os.path.join(static_file_path, course_name, 'manifest.json')
        index_key = "index.{}".format(os.environ.get('FILE_TYPE'))
        lock_f = os.path.join(static_file_path, course_name+'.lock')
        lock = FileLock(lock_f)
        try:
            with lock.acquire(timeout=1):
                with open(manifest_file, 'r') as f:
                    manifest_srv = json.load(f)

            if request.get_json().get("index_mtime") <= manifest_srv[index_key]['mtime']:
                raise PermissionError('Abort: the client version is older than server version')

            os.rename(course_dir, course_dir+'_old')
            os.rename(temp_course_dir, course_dir)
            shutil.rmtree(course_dir+'_old')
            os.remove(lock_f)
        # except Timeout:
        #     print('another process is running')
        #     time.sleep(5)
        # if another error raises
        except:
            logger.debug(traceback.format_exc())
            # shutil.rmtree(temp_course_dir)
            os.remove(lock_f)
            return BadRequest(traceback.format_exc())

    return jsonify({
        'course_instance': auth['sub'],
        'msg': 'The course is successfully uploaded'
    }), 200


if __name__ == '__main__':
    if os.getenv('FLASK_ENV') == 'development':
        app.run(debug=True, host='0.0.0.0', port=9000)
    else:
        app.run()



