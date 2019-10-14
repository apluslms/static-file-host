import os
import sys
import traceback
import logging
import shutil
import tarfile

from flask import request
from werkzeug.exceptions import HTTPException


logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------------------------------------------------------
# Upload handlers

def whether_can_upload(content_type, course_dir, temp_course_dir):
    """ Check that whether the request data can be uploaded
    """

    # get the modification time of index.yaml file in the uploaded directory
    # (the building time of the uploaded dir)
    if content_type == 'application/octet-stream':
        try:
            index_mtime = float(request.headers['Index-Mtime'])
        except:
            logger.info(traceback.format_exc())
            raise
    elif content_type.startswith('multipart/form-data'):
        try:
            index_mtime = float(request.form['index_mtime'])
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


def upload_octet_stream(temp_course_dir):
    """ Upload file data posted by a request with octet-stream content-type to the temp course directory
    """

    # parse data
    try:
        data = request.data
        print(data)
        os.makedirs(temp_course_dir, exist_ok=True)

        # write the compressed file
        temp_compressed = os.path.join(temp_course_dir,
                                       'temp_' + request.headers['File-Index'] + '.tar.gz')

        with open(temp_compressed, 'ab') as f:
            f.seek(0, os.SEEK_END)
            file_size = f.tell()
            if request.headers['Chunk-Index'] == str(file_size):
                f.write(data)

        if 'Last-Chunk' in request.headers:  # The entire compressed file has been uploaded
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
            chunk_size = 4096
            while True:
                chunk = file.stream.read(chunk_size)
                if len(chunk) == 0:
                    break
                f.write(chunk)
    else:
        # write the compressed file
        os.makedirs(temp_course_dir, exist_ok=True)
        temp_compressed = os.path.join(temp_course_dir, 'temp.tar.gz')
        with open(temp_compressed, 'wb') as f:
            chunk_size = 4096
            while True:
                chunk = file.stream.read(chunk_size)
                if len(chunk) == 0:
                    break
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


class ImproperlyConfigured(HTTPException):
    pass


def error_print():
    return '{}. {}, line: {}'.format(sys.exc_info()[0],
                                     sys.exc_info()[1],
                                     sys.exc_info()[2].tb_lineno)







