import os
import sys
import traceback
import logging
from functools import partial, wraps
import shutil
import tarfile

import jwt
from flask import current_app

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------------------------------------------------------
# JWT Authentication


def setting_in_bytes(name):
    value = getattr(current_app.config, name)
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode('utf-8')
    raise ImproperlyConfigured(
        "Value for settings.%s is not bytes or str."
        % (name,))


def prepare_decoder():
    options = {'verify_' + k: True for k in ('iat', 'iss')}
    options.update({'require_' + k: True for k in ('iat',)})
    if hasattr(settings, 'JWT_ISSUER'):
        options['issuer'] = settings.JWT_ISSUER

    if hasattr(settings, 'JWT_PUBLIC_KEY'):
        try:
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives.serialization import load_pem_public_key
        except ImportError as error:
            raise ImproperlyConfigured(
                "`mooc-grader api` requires `cryptography` when using settings.JWT_PUBLIC_KEY: %s"
                % (error,))
        pem = setting_in_bytes('JWT_PUBLIC_KEY')
        try:
            key = load_pem_public_key(pem, backend=default_backend())
        except ValueError as error:
            raise ImproperlyConfigured(
                "Invalid public key in JWT_PUBLIC_KEY: %s"
                % (error,))
        return partial(jwt.decode,
                       key=key,
                       algorithms=settings.JWT_ALGORITHM,
                       **options)
    return None


jwt_decode = prepare_decoder()


def jwt_auth(request):

    if prepare_decoder is None:
        raise ImproperlyConfigured(
            "Received request to %s.api without JWT_PUBLIC_KEY in django settings."
            % (__name__,))

    # require authentication header
    if 'HTTP_AUTHORIZATION' not in request.META:
        logger.debug("JWT auth failed: No authorization header")
        raise PermissionDenied("No authorization header")
    try:
        scheme, token = request.META['HTTP_AUTHORIZATION'].strip().split(' ', 1)
        if scheme.lower() != 'bearer': raise ValueError()
    except ValueError:
        logger.debug("JWT auth failed: Invalid authorization header: %r",
                     request.META.get('HTTP_AUTHORIZATION', ''))
        raise PermissionDenied("Invalid authorization header")

    # decode jwt token
    try:
        return jwt_decode(token)
    except jwt.InvalidTokenError as exc:
        logger.debug("JWT auth failed: %s", exc)
        raise PermissionDenied(str(exc))


def course_manage_required(func):
    """
    Decorator for authenticating jwt token and checking whether a file of a course can be uploaded
    """

    @wraps(func)
    def wrapper(request, *args, **kwargs):

        course_name = kwargs.get('course_name', None)
        if not course_name:
            raise PermissionDenied('No valid course name provided')

        auth = jwt_auth(request)

        # check the payload
        if ('sub' not in auth) or (not auth['sub'].strip()):
            return HttpResponseBadRequest("Invalid payload")
        assert auth['sub'].strip() == course_name, 'the course name in the url does not match the jwt token'

        kwargs['auth'] = auth
        return func(request, *args, **kwargs)

    return wrapper

# ----------------------------------------------------------------------------------------------------------------------
# Upload handlers


def whether_can_upload(request, content_type, course_dir, temp_course_dir):
    """ Check that whether the request data can be uploaded
    """

    # get the modification time of index.yaml file in the uploaded directory
    # (the building time of the uploaded dir)
    if content_type == 'application/octet-stream':
        try:
            index_mtime = float(request.META['HTTP_INDEX_MTIME'])
        except:
            logger.info(traceback.format_exc())
            raise
    elif content_type.startswith('multipart/form-data'):
        try:
            index_mtime = float(request.POST['index_yaml_mtime'])
        except:
            logger.info(traceback.format_exc())
            raise
    else:
        raise ValueError('Error: Unsupported content-type')

    # the course already exists in the grader
    if os.path.exists(course_dir):
        dir_mtime = os.path.getmtime(course_dir)
        # the uploaded directory should be newer than the course directory in the grader

        if index_mtime < dir_mtime:
            raise Exception('Error; The uploaded directory is older than the current directory')

    # a temp course directory exists,
    # meaning that a uploading process is on the halfway
    if os.path.exists(temp_course_dir):
        temp_dir_ctime = os.path.getctime(temp_course_dir)
        # if the uploaded directory is later than temp course dir
        # another uploading process is prior
        if index_mtime > temp_dir_ctime:
            raise Exception('Error: Another uploading process is prior')


def upload_octet_stream(request, temp_course_dir):
    """ Upload file data posted by a request with octet-stream content-type to the temp course directory
    """

    # parse data
    try:
        data = request.body
        os.makedirs(temp_course_dir, exist_ok=True)

        # write the compressed file
        temp_compressed = os.path.join(temp_course_dir,
                                       'temp_' + request.META['HTTP_FILE_INDEX'] + '.tar.gz')

        with open(temp_compressed, 'ab') as f:
            f.seek(0, os.SEEK_END)
            file_size = f.tell()
            if request.META['HTTP_CHUNK_INDEX'] == str(file_size):
                f.write(data)

        if 'HTTP_LAST_CHUNK' in request.META:  # The entire compressed file has been uploaded
            # extract the compressed file to a 'temp' dir
            with tarfile.open(temp_compressed, "r:gz") as tf:
                tf.extractall(temp_course_dir)

            os.remove(temp_compressed)  # Delete the compressed file
    except:
        logger.info(traceback.format_exc())
        raise


def upload_form_data(data, file, temp_course_dir):
    """ Upload file data posted by a request with form-data content-type to the temp course directory
    """

    # write the non-compression file
    if 'compression_file' not in data:
        file_name = os.path.join(temp_course_dir, data['file_name'])
        os.makedirs(os.path.dirname(file_name), exist_ok=True)
        with open(file_name, 'wb') as f:
            for chunk in file.chunks():
                f.write(chunk)
    else:
        # write the compressed file
        os.makedirs(temp_course_dir, exist_ok=True)
        temp_compressed = os.path.join(temp_course_dir, 'temp.tar.gz')
        with open(temp_compressed, 'wb') as f:
            for chunk in file.chunks():
                f.write(chunk)

        # extract the compression file
        with tarfile.open(temp_compressed, "r:gz") as tf:
            tf.extractall(temp_course_dir)

        os.remove(temp_compressed)  # delete the compression file


def update_course_dir(course_dir, temp_course_dir):
    """ Update the course directory from the temp course directory
    """

    if not os.path.exists(course_dir):  # Rename the temp dir
        logger.info('The course directory does not exist before, will be created')
        os.rename(temp_course_dir, course_dir)
    else:  # update the existing course dir (atomic)
        logger.info('The course directory already exists, will be updated')
        os.rename(course_dir, course_dir + '_old')
        os.rename(temp_course_dir, course_dir)
        shutil.rmtree(course_dir + '_old')

# ----------------------------------------------------------------------------------------------------------------------
# Update index.yaml


def url_to_static(request, course_key, path):
    """ Creates an URL for a path in static files """
    return request.build_absolute_uri(
        '{}{}/{}'.format(settings.STATIC_URL, course_key, path))


def url_to_exercise(request, course_key, exercise_key):
    """ Creates an URL for an exercise"""
    return request.build_absolute_uri(
        reverse('exercise', args=[course_key, exercise_key]))


def update_static_url(request, course_key, data):
    """ Update static_content to url"""
    path = data.pop('static_content')
    if isinstance(path, dict):
        url = {
            lang: url_to_static(request, course_key, p)
            for lang, p in path.items()
        }
    else:
        url = url_to_static(request, course_key, path)

    return url


def update_course_index(request, index_data, course_key):
    """ Update course index """
    def children_recursion(parent):
        if "children" in parent:
            for o in [o for o in parent["children"] if "key" in o]:
                if 'config' in o and 'url' not in o:
                    o['url'] = url_to_exercise(request, course_key, o['key'])
                elif "static_content" in o:
                    o['url'] = update_static_url(request, course_key, o)
                children_recursion(o)

    if "modules" in index_data:
        for m in index_data["modules"]:
            children_recursion(m)

    return index_data

# ----------------------------------------------------------------------------------------------------------------------


def error_print():
    return '{}. {}, line: {}'.format(sys.exc_info()[0],
                                     sys.exc_info()[1],
                                     sys.exc_info()[2].tb_lineno)







