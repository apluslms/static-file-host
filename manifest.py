import os
import logging
from operator import itemgetter


logger = logging.getLogger(__name__)


def _sig(st):
    # return (
    #         stat.S_IFMT(st.st_mode),
    #         st.st_size,
    #         st.st_mtime)
    return {"mtime": st.st_mtime,
            "size":  st.st_size}


def get_file_manifest(directory):
    """
    get manifest of files
    :param directory: str, the path of the directory
    :return: a nested dict with rel_file_name as the key and the value is a dict holding the file mtime and the size
    """
    # IGNORE = set(['.git', '.idea', '__pycache__'])

    manifest = dict()

    for basedir, dirs, files in os.walk(directory):
        # dirs[:] = [d for d in dirs if d not in IGNORE]
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for filename in files:
            # if filename.startswith("."):
            #     continue
            file = os.path.join(basedir, filename)
            # file_manifest = {"ctime": os.path.getctime(file),
            #                  "size":  os.path.getsize(file) / (1024 * 1024.0)}
            file_manifest = _sig(os.stat(file))
            manifest[os.path.relpath(file, start=directory)] = file_manifest

    return manifest


def files_to_update_1(manifest_client, manifest_srv, client_basedir):
    """
    :param manifest_client: a nested dict dict[file] = {'size': , 'mtime': } in the client-side
    :param manifest_srv: a nested dict dict[file] = {'size': , 'mtime': } in the server side
    :param client_basedir: base directory of relative file path in the manifest_client dict keys
    :return:
            file_upload: a list of tuples (file_name, file_size) to upload
            file_remove: a list of files to remove
    """
    if not isinstance(manifest_client, dict) or not isinstance(manifest_srv, dict):
        raise TypeError("The manifest is not a dict type")

    client_files, srv_files = set(manifest_client.keys()), set(manifest_srv.keys())

    file_remove = list(srv_files - client_files)
    file_new = list(client_files - srv_files)

    file_inter = list(client_files.intersection(srv_files))
    file_update = [f for f in file_inter if manifest_client[f]["mtime"] > manifest_srv[f]["mtime"]]

    file_upload_list = file_new + file_update

    file_upload = [(os.path.join(client_basedir, f), manifest_client[f]['size']) for f in file_upload_list]

    file_upload.sort(key=itemgetter(1), reverse=True)

    return file_upload, file_remove


def files_to_update_2(manifest_client, manifest_srv, client_basedir):
    files = sorted([f for f in manifest_client if f not in manifest_srv or
                   manifest_client[f]["mtime"] > manifest_srv[f]["mtime"]])

    if len(files) == len(manifest_client) and files:
        return [(client_basedir, os.path.getsize(client_basedir))]

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

    file_upload = [(os.path.join(client_basedir, f),
                    os.path.getsize(os.path.join(client_basedir, f))) for f in list(filtered)]

    file_upload.sort(key=itemgetter(1), reverse=True)

    return file_upload
