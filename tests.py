import glob
import os
import pprint
from utils import check_static_directory
from operator import itemgetter
from timeit import timeit
import fnmatch

course = "/u/71/qinq1/unix/Desktop/def_course"


def main():

    os.environ['PLUGIN_API'] = 'http://0.0.0.0:5000/'
    os.environ['PLUGIN_TOKEN'] = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJkZWZfY291cnNlIiwiaWF0IjoxNTYyODI4MzA0LCJpc3MiOiJzaGVwaGVyZCJ9.MUkoD27P6qZKKMM5juL0e0pZl8OVH6S17N_ZFzC7D0cwOgbcDaAO3S1BauXzhQOneChPs1KEzUxI2dVF-Od_gpN8_IJEnQnk25XmZYecfdoJ5ST-6YonVmUMzKP7UAcvzCFye7mkX7zJ1ADYtda57IUdyaLSPOWnFBSHX5B4XTzzPdVZu1xkRtb17nhA20SUg9gwCOPD6uLU4ml1aOPHBdiMLKz66inI8txPrRK57Gn33m8lVp0WTOOgLV5MkCIpkgVHBl50EHcQFA5KfPet3FBLjpp2I1yThQe_n1Zc6GdnR0v_nqX0JhmmDMOvJ5rhIHZ7B0hEtFy9rKUWOWfcug'
    os.environ['PLUGIN_COURSE'] = 'def_course'
    course_dir = '/u/71/qinq1/unix/Desktop/my_new_course'

    if 'PLUGIN_API' in os.environ and 'PLUGIN_TOKEN' in os.environ and 'PLUGIN_COURSE' in os.environ:
        upload_url = os.environ['PLUGIN_API'] + os.environ['PLUGIN_COURSE'] + '/upload'
        
        static_dir, index_html, index_mtime = check_static_directory(course_dir)
        
        # upload_directory(static_dir, upload_url, index_mtime)
    else:
        raise ValueError('No API or JWT token provided')


def print_dir():
    pp = pprint.PrettyPrinter(indent=4)

    for dir_tuple in os.walk(course):
        # print("basedir:", basedir)
        # if basedir.startswith("."):
        #     continue
        # print("dirs:", dirs)
        # print("files: ", files)
        if dir_tuple[0].startswith("."):
            continue
        pp.pprint(dir_tuple)


def child_dirs(path):
    cd = os.getcwd()  # save the current working directory
    os.chdir(path)  # change directory
    dirs = glob.glob("**/", recursive=True)  # get all the subdirectories
    os.chdir(cd)  # change directory to the script original location
    return dirs


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


# own
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


# Pinja's origin
def files_to_update_21(manifest_client, manifest_srv, client_basedir):
    files = sorted([f for f in manifest_client if f not in manifest_srv or
                   manifest_client[f]["mtime"] > manifest_srv[f]["mtime"]])

    filtered = set()

    if len(files) == len(manifest_client) and files:
        return [(client_basedir, os.path.getsize(client_basedir))]

    subfolder_level = 1

    # go through folders one 'level' at a time, if everything in a folder
    # is going to be copied, we'll just copy the folder instead of files individually
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


# Pinja's modified version
def files_to_update_22(manifest_client, manifest_srv, client_basedir):

    files = sorted([f for f in manifest_client if f not in manifest_srv or
                    manifest_client[f]["mtime"] > manifest_srv[f]["mtime"]])

    filtered = set()

    if len(files) == len(manifest_client) and files:
        return [(client_basedir, os.path.getsize(client_basedir))]

    subfolder_level = 1

    # go through folders one 'level' at a time, if everything in a folder
    # is going to be copied, we'll just copy the folder instead of files individually
    while files:
        filtered = filtered.union({f for f in files if f.count(os.sep) < subfolder_level})  # files in this level
        files = [f for f in files if f.count(os.sep) >= subfolder_level]  # files in the subdirs of this level
        folders = {os.path.dirname(f) for f in files if f.count(os.sep) == subfolder_level}  # subdirs in this level
        for folder in folders:
            # update_whole_folder = (
            #         len([f for f in files if folder in f]) ==
            #         len([f for f in manifest_client if folder in f]))
            update_whole_folder = (len(fnmatch.filter(files, folder+os.sep+'*')) ==
                                   len(fnmatch.filter(list(manifest_client.keys()), folder+os.sep+'*')))
            if update_whole_folder:
                # files = [f for f in files if folder not in f]
                files = [f for f in files if not fnmatch.fnmatch(f, folder+os.sep+'*')]
                filtered.add(folder)
            else:
                files_in_folder = {f for f in files
                                   if fnmatch.fnmatch(f, folder+os.sep+'*')
                                   and f.count(os.sep) == subfolder_level}
                files = [f for f in files if f not in files_in_folder]
                filtered = filtered.union(files_in_folder)
        subfolder_level += 1

    file_upload = [(os.path.join(client_basedir, f),
                    os.path.getsize(os.path.join(client_basedir, f))) for f in list(filtered)]

    file_upload.sort(key=itemgetter(1), reverse=True)

    return file_upload


def files_to_update_3(manifest_client, manifest_srv, client_basedir):

    def test(filtered, file_list, folder):
        # level = root.replace(startpath, '').count(os.sep)
        level = folder.count(os.sep)
        print(folder, level)
        filtered = filtered.union({f for f in file_list if f.count(os.sep) == level})  # files in this level
        files_next_level = {f for f in file_list if f.count(os.sep) == (level+1)}  # files in the subdirs of this level
        print(filtered)
        print(files_next_level)

        if files_next_level:
            folders = {os.path.dirname(f) for f in files_next_level}  # subdirs in this level

            for folder in folders:
                # update_whole_folder = (
                #         len([f for f in files if folder in f]) ==
                #         len([f for f in manifest_client if folder in f]))
                all_files_in_folder = fnmatch.filter(file_list, folder + os.sep + '*')
                update_whole_folder = (len(all_files_in_folder) ==
                                       len(fnmatch.filter(list(manifest_client.keys()), folder + os.sep + '*')))
                if update_whole_folder:
                    # files = [f for f in files if folder not in f]
                    # files = [f for f in files if not fnmatch.fnmatch(f, folder+os.sep+'*')]
                    filtered.add(folder)
                    file_list = file_list - set(all_files_in_folder)
                else:
                    files_in_folder = {f for f in files_next_level if fnmatch.fnmatch(f, folder+os.sep+'*')}
                    filtered = filtered.union(files_in_folder)
                    file_list = file_list - files_in_folder

                    filtered, file_list = test(filtered, file_list, folder)
        return filtered, file_list

    files = set(sorted([f for f in manifest_client if f not in manifest_srv or
                        manifest_client[f]["mtime"] > manifest_srv[f]["mtime"]]))

    # if len(files) == len(manifest_client.keys()):
    #     return [(client_basedir, os.path.getsize(client_basedir))]

    update = set()
    update, files = test(update, files, '')
    print(update)
    print(files)

    return update, files


# file_upload = [(os.path.join(client_basedir, f), manifest_client[f]['size']) for f in file_upload_list]
# file_upload.sort(key=itemgetter(1), reverse=True)
# return file_upload, file_remove


def wrapper(func, *args, **kwargs):

    def wrapped():
        return func(*args, **kwargs)

    return wrapped


manifest = get_file_manifest(course)


def test_speed():
    print("upload the whole course")

    print("own")
    wrapped1 = wrapper(files_to_update_1, manifest, {}, course)
    print(timeit(wrapped1, number=1))

    print("Pinja's origin")
    wrapped21 = wrapper(files_to_update_21, manifest, {}, course)
    print(timeit(wrapped21, number=1))

    print("Pinja's modified")
    wrapped22 = wrapper(files_to_update_22, manifest, {}, course)
    print(timeit(wrapped22, number=1))

    print("*"*180)
    print("upload the selected files")

    print("own")
    wrapped1 = wrapper(files_to_update_1, manifest,
    {'static_upload.sh': {'mtime': 1572866559.30007, 'size': 655}}, course)
    print(timeit(wrapped1, number=1))

    print("Pinja's origin")
    wrapped21 = wrapper(files_to_update_21, manifest,
    {'static_upload.sh': {'mtime': 1572866559.30007, 'size': 655}}, course)
    print(timeit(wrapped21, number=1))

    print("Pinja's modified")
    wrapped22 = wrapper(files_to_update_22, manifest,
    {'static_upload.sh': {'mtime': 1572866559.30007, 'size': 655}}, course)
    print(timeit(wrapped22, number=1))


# file_upload  = files_to_update_3(manifest, {}, course)
# file_upload = files_to_update_3(manifest, {'static_upload.sh':{'mtime': 1572866559.30007, 'size': 655}}, course)
# print(file_upload)
# filtered, files = files_to_update_3(manifest, {}, course)
files_to_update_3(manifest, {}, course)

# files_to_update_3(manifest, {'static_upload.sh': {'mtime': 1572866559.30007, 'size': 655}}, course)

# test_speed()