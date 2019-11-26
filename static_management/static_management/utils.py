import os
import sys
import traceback
import logging
import shutil
import tarfile
import errno
from time import ctime

from flask import request
from werkzeug.exceptions import HTTPException

import static_management.locks as locks

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
        raise


def upload_form_data(file, temp_course_dir):
    """ Upload file data posted by a request with form-data content-type to the temp course directory
    """
    try:
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
    except:
        raise


def update_course_dir(course_dir, temp_course_dir):
    """ Update the course directory from the temp course directory
    """
    if not os.path.exists(course_dir):  # Rename the temp dir
        logger.info('The course directory does not exist before, will be created')
        try:
            os.rename(temp_course_dir, course_dir)
        except:
            shutil.rmtree(temp_course_dir)
            raise
    else:  # update the existing course dir (atomic)
        logger.info('The course directory already exists, will be updated')
        try:
            os.rename(course_dir, course_dir + '_old')
        except:
            shutil.rmtree(temp_course_dir)
            raise
        try:
            os.rename(temp_course_dir, course_dir)
        except:
            shutil.rmtree(temp_course_dir)
            os.rename(course_dir + '_old', course_dir)
            raise
        # shutil.rmtree(course_dir + '_old')


def _samefile(src, dst):
    # Macintosh, Unix.
    if hasattr(os.path, 'samefile'):
        try:
            return os.path.samefile(src, dst)
        except OSError:
            return False

    # All other platforms: check for same pathname.
    return (os.path.normcase(os.path.abspath(src)) ==
            os.path.normcase(os.path.abspath(dst)))


def file_move_safe(old_file_name, new_file_name, chunk_size=1024 * 64, allow_overwrite=True):
    """
    Move a file from one location to another in the safest way possible.
    First, try ``os.rename``, which is simple but will break across filesystems.
    If that fails, stream manually from one file to another in pure Python.
    If the destination file exists and ``allow_overwrite`` is ``False``, raise
    ``FileExistsError``.
    """
    # There's no reason to move if we don't have to.
    if _samefile(old_file_name, new_file_name):
        return

    try:
        if not allow_overwrite and os.access(new_file_name, os.F_OK):
            raise FileExistsError('Destination file %s exists and allow_overwrite is False.' % new_file_name)

        # os.rename(old_file_name, new_file_name)
        os.replace(old_file_name, new_file_name)
        return
    except OSError:
        # OSError happens with os.rename() if moving to another filesystem or
        # when moving opened files on certain operating systems.
        pass

    # first open the old file, so that it won't go away
    with open(old_file_name, 'rb') as old_file:
        # now open the new file, not forgetting allow_overwrite
        fd = os.open(new_file_name, (os.O_WRONLY | os.O_CREAT | getattr(os, 'O_BINARY', 0) |
                                     (os.O_EXCL if not allow_overwrite else 0)))
        try:
            locks.lock(fd, locks.LOCK_EX)
            current_chunk = None
            while current_chunk != b'':
                current_chunk = old_file.read(chunk_size)
                os.write(fd, current_chunk)
        finally:
            locks.unlock(fd)
            os.close(fd)

    try:
        shutil.copystat(old_file_name, new_file_name)
    except PermissionError as e:
        # Certain filesystems (e.g. CIFS) fail to copy the file's metadata if
        # the type of the destination filesystem isn't the same as the source
        # filesystem; ignore that.
        if e.errno != errno.EPERM:
            raise

    try:
        os.remove(old_file_name)
    except PermissionError as e:
        # Certain operating systems (Cygwin and Windows)
        # fail when deleting opened files, ignore it.  (For the
        # systems where this happens, temporary files will be auto-deleted
        # on close anyway.)
        if getattr(e, 'winerror', 0) != 32:
            raise


def update_course_dir2(course_dir, temp_course_dir):

    # if not os.path.exists(course_dir):  # Rename the temp dir
    #     logger.info('The course directory does not exist before, will be created')
    #     try:
    #         os.rename(temp_course_dir, course_dir)
    #     except:
    #         shutil.rmtree(temp_course_dir)
    #         raise
    # else:  # update the existing course dir (atomic)
    #     logger.info('The course directory already exists, will be updated')
    #
    #     manifest_compare = dict()
    #     for basedir, dirs, files in os.walk(temp_course_dir):
    #         for filename in files:
    #             old_file_path = os.path.join(basedir, filename)
    #             rel_file_path = os.path.relpath(old_file_path, start=temp_course_dir)
    #             new_file_path = os.path.join(course_dir, rel_file_path)
    #             manifest_compare[rel_file_path] = {"old": ctime(os.path.getctime(old_file_path))}
    #             file_move_safe(old_file_path, new_file_path)
    #             manifest_compare[rel_file_path]["new"] = ctime(os.path.getctime(new_file_path))
    #
    #     print("manifest comparison before and after update:")
    #     for k, v in manifest_compare.items():
    #         print(k, v)

    try:
        if not os.path.exists(course_dir):  # Rename the temp dir
            logger.info('The course directory does not exist before, will be created')
            os.rename(temp_course_dir, course_dir)
        else:
            # update the existing course dir (atomic)
            logger.info('The course directory already exists, will be updated')
            manifest_compare = dict()
            for basedir, dirs, files in os.walk(temp_course_dir):
                for filename in files:
                    old_file_path = os.path.join(basedir, filename)
                    rel_file_path = os.path.relpath(old_file_path, start=temp_course_dir)
                    new_file_path = os.path.join(course_dir, rel_file_path)
                    manifest_compare[rel_file_path] = {"old": ctime(os.path.getctime(old_file_path))}
                    file_move_safe(old_file_path, new_file_path)
                    manifest_compare[rel_file_path]["new"] = ctime(os.path.getctime(new_file_path))
            print("manifest comparison before and after update:")
            for k, v in manifest_compare.items():
                print(k, v)
    except:
        raise

# ----------------------------------------------------------------------------------------------------------------------


class ImproperlyConfigured(HTTPException):
    pass


def error_print():
    return '{}. {}, line: {}'.format(sys.exc_info()[0],
                                     sys.exc_info()[1],
                                     sys.exc_info()[2].tb_lineno)







