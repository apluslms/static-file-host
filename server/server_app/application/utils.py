import os
import sys
import logging
import shutil
import tarfile
import errno
import pprint

from flask import request
from werkzeug.exceptions import HTTPException

import application.locks as locks

FILE_TYPE1 = ['yaml', 'html']

pp = pprint.PrettyPrinter(indent=4)
logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------------------------------------------------------
# File info handler


def compare_files_to_update(manifest_client, manifest_srv):
    """ Get list of the files to update
    :param manifest_client: a nested dict dict[file] = {'size': , 'mtime': } in the client-side (a specific course)
    :param manifest_srv: a nested dict dict[file] = {'size': , 'mtime': } in the server side
    :return:
            a nested dict containing the files of newly added, updated and removed
    """
    if not isinstance(manifest_client, dict) or not isinstance(manifest_srv, dict):
        raise TypeError("The manifest is not a dict type")

    client_files, srv_files = set(manifest_client.keys()), set(manifest_srv.keys())

    files_remove = list(srv_files - client_files)
    files_new = {f: manifest_client[f] for f in list(client_files - srv_files)}

    files_inter = client_files.intersection(srv_files)
    files_replace = {f: manifest_client[f] for f in files_inter
                     if manifest_client[f]["mtime"] > manifest_srv[f]["mtime"]}
    files_keep = list(files_inter - set(files_replace.keys()))

    files_to_update = {'files_new': files_new,
                       'files_update': files_replace,
                       'files_keep': files_keep,
                       'files_remove': files_remove}

    return files_to_update


def whether_can_renew(manifest_srv, manifest_client):

    if os.environ.get("SERVER_FILE") in FILE_TYPE1:
        # check whether the index mtime is earlier than the one in the server
        index_key = "index.{}".format(os.environ.get("SERVER_FILE"))
        flag = manifest_client[index_key]['mtime'] > manifest_srv[index_key]['mtime']
    else:
        latest_mtime_srv = max(file['mtime'] for file in manifest_srv.values())
        latest_mtime_client = max(file['mtime'] for file in manifest_client.values())
        flag = latest_mtime_client > latest_mtime_srv

    return flag
# ----------------------------------------------------------------------------------------------------------------------
# Upload handlers


def upload_octet_stream(temp_course_dir):
    """ Download file data posted by a request with octet-stream content-type to the temp course directory
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


# ----------------------------------------------------------------------------------------------------------------------
# Error handling

class ImproperlyConfigured(HTTPException):
    pass


def error_print():
    return '{}. {}, line: {}'.format(sys.exc_info()[0],
                                     sys.exc_info()[1],
                                     sys.exc_info()[2].tb_lineno)







