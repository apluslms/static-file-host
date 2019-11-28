import os
import logging
from operator import itemgetter


logger = logging.getLogger(__name__)


def files_sizes_list(directory):
    """ Get a list of tuples of file path and size in a directory, sorted by the file size (largest to smallest)
    """
    all_files = [os.path.join(basedir, filename) for basedir, dirs, files in os.walk(directory) for filename in files]
    # list of tuples of file path and size (MB), e.g., ('/Path/to/the.file', 1.0)
    files_and_sizes = [(os.path.relpath(path, start=directory),
                        os.path.getsize(path) / (1024 * 1024.0)) for path in all_files]
    files_and_sizes.sort(key=itemgetter(1), reverse=True)

    return files_and_sizes


def get_file_manifest(directory):
    """
    get manifest of files
    :param directory: str, the path of the directory
    :return: a nested dict with rel_file_name as the key and the value is a dict holding the file ctime and the size
    """
    manifest = dict()

    for basedir, dirs, files in os.walk(directory):
        for filename in files:
            file = os.path.join(basedir, filename)
            # file_manifest = (os.path.getctime(file), os.path.getsize(file) / (1024 * 1024.0))
            file_manifest = {"ctime": os.path.getctime(file),
                             "size":  os.path.getsize(file) / (1024 * 1024.0)}
            manifest[os.path.relpath(file, start=directory)] = file_manifest

    return manifest


def compare_manifest(manifest_client, manifest_srv):
    if not isinstance(manifest_client, dict) or not isinstance(manifest_srv, dict):
        raise TypeError("The manifest is not a dict type")

    print("The total number of files in the client side: ", len(manifest_client))

    client_files, srv_files = set(manifest_client.keys()), set(manifest_srv.keys())
    file_inter = list(client_files.intersection(srv_files))
    file_update = list(client_files - srv_files)
    file_remove = list(srv_files - client_files)

    file_upload = [(file, manifest_client[file]['size']) for file in file_update]

    for file in file_inter:
        if manifest_client[file]["ctime"] > manifest_srv[file]["ctime"]:
            file_upload.append((file, manifest_client[file]['size']))

    file_upload.sort(key=itemgetter(1), reverse=True)

    return file_upload, file_remove
