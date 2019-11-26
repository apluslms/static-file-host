import os
import requests
from io import BytesIO
import json
# import dictdiffer

from utils import (check_static_directory,
                   get_file_manifest,
                   upload_directory,
                   error_print,
                   upload_files,
                   )


def compare_manifest(manifest_client, manifest_srv):
    if not isinstance(manifest_client, dict) or not isinstance(manifest_srv, dict):
        raise TypeError("The manifest is not a dict type")

    print("The total size of files: ", len(list(manifest_client.keys())))

    client_files, srv_files = set(manifest_client.keys()), set(manifest_srv.keys())
    file_inter = list(client_files.intersection(srv_files))
    file_update = list(client_files - srv_files)
    file_remove = list(srv_files - client_files)

    file_upload = [(file, manifest_client[file]['size']) for file in file_update]

    for file in file_inter:
        if manifest_client[file]["ctime"] > manifest_srv[file]["ctime"]:
            file_upload.append((file, manifest_client[file]['size']))
        # else:
        #     print(file, " client: ", manifest_client[file]["ctime"], " server: ", manifest_srv[file]["ctime"])

    return file_upload, file_remove


# def compare_manifest_2(manifest_client, manifest_srv):
#     for diff in list(dictdiffer.diff(manifest_client, manifest_srv)):
#         file_upload = list()
#         file_remove = list()
#         if diff[0] == "ADD":
#             file_remove.append(diff[2][0])
#         elif diff[0] == "REMOVE":
#             file_upload.append(diff[2][0])
#         elif diff[0] == "CHANGE":
#             if diff[2][0] > diff[2][1]:
#                 file_upload.append(diff[1])
#
#         return file_upload, file_remove


def main():

    if not ({'PLUGIN_API', 'PLUGIN_TOKEN', 'PLUGIN_COURSE'} <= os.environ.keys()):
        raise ValueError('No API or JWT token provided')

    upload_url = os.environ['PLUGIN_API'] + os.environ['PLUGIN_COURSE'] + '/upload'

    static_dir, index_html, index_mtime = check_static_directory(os.getcwd())

    manifest_client = get_file_manifest(static_dir)
    # print(manifest_client)

    manifest_url = os.environ['PLUGIN_API'] + os.environ['PLUGIN_COURSE'] + '/file_manifest'

    # Create the in-memory file-like object
    buffer = BytesIO()
    buffer.write(json.dumps(manifest_client).encode('utf-8'))

    headers = {
        'Authorization': 'Bearer {}'.format(os.environ['PLUGIN_TOKEN'])
    }

    # get the manifest of files in the server side
    manifest_r = requests.post(manifest_url, headers=headers)

    if manifest_r.status_code != 200:
        return requests.HTTPError(manifest_r.text)

    try:
        if not manifest_r.json().get("exist"):
            upload_directory(static_dir, upload_url, index_mtime)
        else:
            print("The course already exists")
            manifest_srv = manifest_r.json().get("manifest_srv")
            # print(manifest_srv)
            file_upload, file_remove = compare_manifest(manifest_client, manifest_srv)
            print("number of uploaded files: ", len(file_upload), ",num of deleted files:", len(file_remove))
            # print(file_upload)
            # print(file_remove)
            # print(list(filter(lambda i: i[0] in file_remove, manifest_srv.items())))
            # print(dict(filter(lambda i: i[0] in file_remove, manifest_srv.items())))
            upload_files(file_upload, static_dir, upload_url, index_mtime)
    except:
        return requests.HTTPError(error_print())


if __name__ == "__main__":
    main()
