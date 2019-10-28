import os
import logging
import traceback

from flask import request, jsonify
import jwt
from werkzeug.exceptions import BadRequest, Unauthorized

from static_management import (
    app,
    prepare_decoder,
)
from static_management.utils import (
    whether_can_upload,
    upload_octet_stream,
    upload_form_data,
    update_course_dir,
    error_print,
    ImproperlyConfigured,
)


logger = logging.getLogger(__name__)

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


@app.route('/<course_name>/upload', methods=['GET', 'POST'])
def static_upload(course_name):
    """
        Upload/Update static files of a course
    """
    print(request.headers)
    auth = authenticate()

    # the absolute path of the course in the server
    static_file_path = app.config.get('STATIC_FILE_PATH')
    if not static_file_path:
        return ImproperlyConfigured('STATIC_FILE_PATH not configured')

    course_directory = os.path.join(static_file_path, course_name)

    message = None  # The message in response

    # check request content-type
    content_type = request.content_type

    if not (content_type == 'application/octet-stream' or
            content_type.startswith('multipart/form-data')):
        logger.warning(content_type)
        return BadRequest("Unsupported content-type")

    temp_course_dir = os.path.join(static_file_path, 'temp_' + course_name)
    # check whether the data can be uploaded
    try:
        whether_can_upload(content_type, course_directory, temp_course_dir)
    except:
        return BadRequest(error_print())

    # upload/ update the courses files of a course
    try:
        if content_type == 'application/octet-stream':

            upload_octet_stream(temp_course_dir)

            if 'Last-File' in request.headers:
                update_course_dir(course_directory, temp_course_dir)
                message = 'Upload the course {} successfully'.format(auth['sub'].strip())

        elif content_type.startswith('multipart/form-data'):

            data, file = request.form, request.files['file']
            upload_form_data(data, file, temp_course_dir)

            if 'last_file' in data:
                update_course_dir(course_directory, temp_course_dir)
                message = 'Upload the course {} successfully'.format(course_name)
    except:
        logger.info(traceback.format_exc())
        return BadRequest(error_print())

    return jsonify({
        'course_instance': auth['sub'],
        'status': 'success',
        'message': message
    }), 200


if __name__ == '__main__':
    app.run()
else:
    application = app
