import os
import sys
import math
import json
import traceback
import logging
import shutil
import tarfile
import errno
import pprint

from flask import request, current_app
from werkzeug.exceptions import HTTPException

import management.locks as locks


pp = pprint.PrettyPrinter(indent=4)
logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------------------------------------------------------
# Get list of the files to update


def files_to_update_1(manifest_client, manifest_srv):
    """
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

    files_inter = list(client_files.intersection(srv_files))
    files_update = {f: manifest_client[f] for f in files_inter
                    if not math.isclose(manifest_client[f]["mtime"], manifest_srv[f]["mtime"])}

    # print("The number of intersection of files: ", len(files_inter))
    # print("The number of updated files: ", len(files_update))
    # files_inter_dict = dict()
    # for f in files_inter:
    #     files_inter_dict[f] = {"client": manifest_client[f]["mtime"],
    #                            "server": manifest_srv[f]["mtime"]}
    # files_update_dict = dict()
    # for f in list(files_update.keys()):
    #     files_update_dict[f] = {"client": manifest_client[f]["mtime"],
    #                             "server": manifest_srv[f]["mtime"]}
    #
    # print("Intersection of files")
    # pp.pprint(files_inter_dict)
    # print("Files to update")
    # pp.pprint(files_update_dict)

    files_to_update = {'files_new': files_new, 'files_update': files_update, 'files_remove': files_remove}

    return files_to_update


def files_to_update_2(manifest_client, manifest_srv):
    # files = sorted([f for f in manifest_client if f not in manifest_srv or
    #                manifest_client[f]["mtime"] > manifest_srv[f]["mtime"]])
    # files = sorted([f for f in manifest_client if f not in manifest_srv or
    #                 (not math.isclose(manifest_client[f]["mtime"], manifest_srv[f]["mtime"])
    #                  and manifest_client[f]["mtime"] > manifest_srv[f]["mtime"])])
    files = sorted([f for f in manifest_client if f not in manifest_srv or
                    not math.isclose(manifest_client[f]["mtime"], manifest_srv[f]["mtime"])])

    if len(files) == len(manifest_client) and files:
        return '.'

    filtered = set()

    # go through folders one 'level' at a time, if everything in a folder
    # is going to be copied, we'll just copy the folder instead of files individually
    subfolder_level = 1
    while files:
        filtered = filtered.union({f for f in files if f.count(os.sep) < subfolder_level})  # files in this level
        files = [f for f in files if f.count(os.sep) >= subfolder_level]  # files in the subdirs of this level
        folders = {os.path.dirname(f) for f in files if f.count(os.sep) == subfolder_level}  # subdirs in this level
        for folder in folders:
            update_whole_folder = (
                    len([f for f in files if folder in f]) ==
                    len([f for f in manifest_client if folder in f]))
            if update_whole_folder:
                files = [f for f in files if folder not in f]
                filtered.add(folder)
            else:
                files_in_folder = {f for f in files
                                   if folder in f and f.count(os.sep) == subfolder_level}
                files = [f for f in files if f not in files_in_folder]
                filtered = filtered.union(files_in_folder)
        subfolder_level += 1

    return list(filtered)

# ----------------------------------------------------------------------------------------------------------------------
# Upload handlers


def whether_can_upload(content_type, course_dir, temp_course_dir):
    """ Check that whether the request data can be downloaded
    """

    # get the modification time of index.yaml file in the client side
    # (the building time of the course to upload)
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

    # the course already exists
    if os.path.exists(course_dir):
        srv_index_mtime = os.path.getmtime(os.path.join(course_dir, 'index.html')) * 1e6
        # the uploaded files should be a newer version
        if math.isclose(index_mtime, srv_index_mtime) or index_mtime < srv_index_mtime:
            raise Exception('Error; The uploaded directory is older than the current directory')

    # a temp course directory exists,
    # meaning that a uploading process is on the halfway
    if os.path.exists(temp_course_dir):
        raise Exception('Error: Another uploading process is prior')


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


def update_course_dir(course_dir, temp_course_dir, files_to_update):
    files_new, files_update, files_remove = (files_to_update['files_new'],
                                             files_to_update['files_update'],
                                             files_to_update['files_remove'])
    basedir, course_name = os.path.split(course_dir)
    manifest_srv_file = os.path.join(current_app.config.get('STATIC_FILE_PATH'), "manifest.json")
    with open(manifest_srv_file, 'r') as f:
        manifest_srv = json.load(f)
    # print("manifest_srv")
    # print(manifest_srv)
    try:
        if not os.path.exists(course_dir) and not files_update and not files_remove:  # Rename the temp dir
            logger.info("The course directory does not exist before, will be added")
            # logger.info('The course directory does not exist before, will be added')
            os.rename(temp_course_dir, course_dir)
            for base, dirs, files in os.walk(course_dir):
                for filename in files:
                    manifest_name = os.path.join(base, filename).replace(basedir+os.sep, '')
                    manifest_srv[manifest_name] = files_new[manifest_name]
            # logger.info("The course is successfully uploaded!")
            # print("Final manifest_srv")
            # pp.pprint(manifest_srv)
            # update the manifest json file (atomic)
            temp_manifest_file = os.path.join(current_app.config.get('STATIC_FILE_PATH'),
                                              "manifest_modifiedby_{}.json".format(course_name))
            with open(temp_manifest_file, 'w') as f:
                json.dump(manifest_srv, f)

            os.replace(temp_manifest_file, manifest_srv_file)

            logger.info("The course is successfully uploaded!")
        else:
            # update the existing course dir (atomic)
            # logger.info('The course directory already exists, will be updated')
            logger.info('The course directory already exists, will be updated')

            # Solution 1: Go through the temp course dir
            # manifest_compare = dict()
            files_upload = {**files_new, **files_update}

            for basedir, dirs, files in os.walk(temp_course_dir):
                for filename in files:
                    old_file_path = os.path.join(basedir, filename)
                    rel_file_path = os.path.relpath(old_file_path, start=temp_course_dir)
                    new_file_path = os.path.join(course_dir, rel_file_path)
                    # print(new_file_path, "old:", ctime(os.path.getmtime(new_file_path)))
                    file_move_safe(old_file_path, new_file_path)
                    # Update the manifest json file
                    manifest_srv[os.path.join(course_name, rel_file_path)] = files_upload[os.path.join(course_name,
                                                                                                       rel_file_path)]
            # # Solution 2: Go through the files_new and files_update dicts
            # for f in list(files_new.keys()):
            #     shutil.move(os.path.join(temp_course_dir,  f.replace(course_name + os.sep, '')),
            #                 os.path.join(basedir, f))
            #     manifest_srv[f] = files_new[f]
            # for f in list(files_update.keys()):
            #     shutil.move(os.path.join(temp_course_dir, f.replace(course_name + os.sep, '')),
            #                 os.path.join(basedir, f))
            #     manifest_srv[f] = files_update[f]

            # if not os.listdir(temp_course_dir):
            shutil.rmtree(temp_course_dir)

            # Remove old files
            for f in files_remove:
                # os.remove(os.path.join(course_dir, f.replace(course_name + os.sep, '')))
                os.remove(os.path.join(basedir, f))
                del manifest_srv[f]

            # update the manifest json file (atomic)
            temp_manifest_file = os.path.join(current_app.config.get('STATIC_FILE_PATH'),
                                              "manifest_modifiedby_{}.json".format(course_name))
            with open(temp_manifest_file, 'w') as f:
                json.dump(manifest_srv, f)

            os.replace(temp_manifest_file, manifest_srv_file)

            logger.info("The course is successfully updated!")
    except:
        raise


# ----------------------------------------------------------------------------------------------------------------------
# Error handling

class ImproperlyConfigured(HTTPException):
    pass


def error_print():
    return '{}. {}, line: {}'.format(sys.exc_info()[0],
                                     sys.exc_info()[1],
                                     sys.exc_info()[2].tb_lineno)







