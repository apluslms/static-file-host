import os
import logging

from flask import Blueprint, request
from flask import current_app


bp = Blueprint('management', __name__)
logger = logging.getLogger(__name__)


@bp.route('/', methods=['GET'])
def static_upload(**kwargs):
    """
        Upload/Update static files of a course
        """
    # the absolute path of the course in the server
    auth = kwargs['auth']
    static_path = current_app.config.STATIC_PATH
    course_name = auth['sub'].strip()
    course_directory = os.path.join(static_path, course_name)

    message = None  # The message in response

    # check request content-type
    content_type = request.mimetype
    print(content_type)
    if not (content_type == 'application/octet-stream' or
            content_type.startswith('multipart/form-data')):
        logger.warning(content_type)
        return HttpResponseBadRequest("Unsupported content-type")

    temp_course_dir = os.path.join(courses_path, 'temp_' + course_name)
    # check whether the data can be uploaded
    try:
        whether_can_upload(request, content_type, course_directory, temp_course_dir)
    except:
        return HttpResponseBadRequest(error_print())

    # upload/ update the course directory in mooc-grader
    try:
        if content_type == 'application/octet-stream':

            upload_octet_stream(request, temp_course_dir)

            if 'HTTP_LAST_FILE' in request.META:
                update_course_dir(course_directory, temp_course_dir)
                message = 'Upload the course {} successfully'.format(auth['sub'].strip())

        elif content_type.startswith('multipart/form-data'):

            data, file = request.POST, request.FILES['file']
            upload_form_data(data, file, temp_course_dir)

            if 'last_file' in data:
                update_course_dir(course_directory, temp_course_dir)
                message = 'Upload the course {} successfully'.format(course_name)
    except:
        logger.info(traceback.format_exc())
        return HttpResponseBadRequest(error_print())

    return JsonResponse({
        'course_instance': auth['sub'],
        'status': 'success',
        'message': message
    }, status=200)


from django.views.decorators.http import require_http_methods
from django.http import (
    JsonResponse,
)
from django.views.decorators.csrf import csrf_exempt

from .course import Course
from .parser import yaml
from .utils import *


@csrf_exempt
@require_http_methods(['POST'])
@course_manage_required
def course_upload(request, *args, **kwargs):
    """
    Upload/Update a course
    """
    # the absolute path of the course in mooc-grader
    auth = kwargs['auth']
    courses_path = settings.COURSES_PATH
    course_name = auth['sub'].strip()
    course_directory = os.path.join(courses_path, course_name)

    message = None  # The message in response

    # check request content-type
    content_type = request.META['CONTENT_TYPE']
    if not (content_type == 'application/octet-stream' or
            content_type.startswith('multipart/form-data')):
        logger.warning(content_type)
        return HttpResponseBadRequest("Unsupported content-type")

    temp_course_dir = os.path.join(courses_path, 'temp_' + course_name)
    # check whether the data can be uploaded
    try:
        whether_can_upload(request, content_type, course_directory, temp_course_dir)
    except:
        return HttpResponseBadRequest(error_print())

    # upload/ update the course directory in mooc-grader
    try:
        if content_type == 'application/octet-stream':

            upload_octet_stream(request, temp_course_dir)

            if 'HTTP_LAST_FILE' in request.META:
                update_course_dir(course_directory, temp_course_dir)
                message = 'Upload the course {} successfully'.format(auth['sub'].strip())

        elif content_type.startswith('multipart/form-data'):

            data, file = request.POST, request.FILES['file']
            upload_form_data(data, file, temp_course_dir)

            if 'last_file' in data:
                update_course_dir(course_directory, temp_course_dir)
                message = 'Upload the course {} successfully'.format(course_name)
    except:
        logger.info(traceback.format_exc())
        return HttpResponseBadRequest(error_print())

    return JsonResponse({
        'course_instance': auth['sub'],
        'status': 'success',
        'message': message
    }, status=200)


@csrf_exempt
@require_http_methods(['DELETE'])
@course_manage_required
def course_delete(request, *args, **kwargs):
    """ Delete a course
    """
    # the absolute path of the course in mooc-grader
    auth = kwargs['auth']
    courses_path = settings.COURSES_PATH
    course_name = auth['sub'].strip()
    course_directory = os.path.join(courses_path, course_name)

    # if the course does not exist
    if not os.path.exists(course_directory):
        return HttpResponseBadRequest("error: The course folder does not exist")

    # delete the course
    shutil.rmtree(course_directory)
    message = 'Delete the course {} successfully'.format(course_name)

    return JsonResponse({
        'course_instance': auth['sub'],
        'status': 'success',
        'message': message
    }, status=200)


@csrf_exempt
@require_http_methods(['DELETE'])
@course_manage_required
def file_delete(request, *args, **kwargs):
    """ Delete a file of a course directory
    """
    # get the path of the course directory
    auth = kwargs['auth']
    courses_path = settings.COURSES_PATH
    course_name = auth['sub'].strip()
    course_directory = os.path.join(courses_path, course_name)
    if not os.path.exists(course_directory):
        return HttpResponseBadRequest('The course directory {} does not exist'.format(course_name))

    # get the path of the file
    rel_file_path = kwargs.get('file_path', None)
    if not rel_file_path:
        return HttpResponseBadRequest('No valid file_path provided')

    file_path = os.path.join(course_directory, rel_file_path)
    if not os.path.exists(file_path):
        return HttpResponseBadRequest('{} does not exist'.format(file_path))

    # remove the file
    os.remove(file_path)
    message = 'Delete the file {} of the course {} successfully'.format(file_path, course_name)

    return JsonResponse({
        'status': 'success',
        'message': message
    }, status=200)
