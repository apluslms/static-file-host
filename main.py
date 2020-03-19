import os
import sys
import requests
from io import BytesIO
import json
import pprint
import logging
import traceback

from upload import upload_to_server
from utils import (get_file_manifest,
                   check_static_directory,
                   examine_env_var,
                   GetFileUpdateError,
                   )

logger = logging.getLogger(__name__)
pp = pprint.PrettyPrinter(indent=4)

# os.environ['PLUGIN_API'] = 'http://0.0.0.0:5000/'
# os.environ['PLUGIN_TOKEN'] = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJkZWZfY291cnNlIiwiaWF0IjoxNTYyODI4MzA0LCJpc3MiOiJzaGVwaGVyZCJ9.MUkoD27P6qZKKMM5juL0e0pZl8OVH6S17N_ZFzC7D0cwOgbcDaAO3S1BauXzhQOneChPs1KEzUxI2dVF-Od_gpN8_IJEnQnk25XmZYecfdoJ5ST-6YonVmUMzKP7UAcvzCFye7mkX7zJ1ADYtda57IUdyaLSPOWnFBSHX5B4XTzzPdVZu1xkRtb17nhA20SUg9gwCOPD6uLU4ml1aOPHBdiMLKz66inI8txPrRK57Gn33m8lVp0WTOOgLV5MkCIpkgVHBl50EHcQFA5KfPet3FBLjpp2I1yThQe_n1Zc6GdnR0v_nqX0JhmmDMOvJ5rhIHZ7B0hEtFy9rKUWOWfcug'
# os.environ['PLUGIN_COURSE'] = 'def_course'
# course_dir = '/u/71/qinq1/unix/Desktop/my_new_course'


def main():

    examine_env_var()
    course_dir = os.getcwd()
    static_dir, index_html, index_mtime = check_static_directory(course_dir)
    manifest_client = get_file_manifest(static_dir)

    # Create the in-memory file-like object storing the manifest
    buffer = BytesIO()
    buffer.write(json.dumps(manifest_client).encode('utf-8'))
    buffer.seek(0)

    get_files_url = os.environ['PLUGIN_API'] + os.environ['PLUGIN_COURSE'] + '/get-files-to-update'
    upload_url = os.environ['PLUGIN_API'] + os.environ['PLUGIN_COURSE'] + '/upload-file'
    finalizer_url = os.environ['PLUGIN_API'] + os.environ['PLUGIN_COURSE'] + '/upload-finalizer'
    headers = {
        'Authorization': 'Bearer {}'.format(os.environ['PLUGIN_TOKEN'])
    }

    # 1. get the manifest of files in the server side
    try:
        get_files_r = requests.post(get_files_url, headers=headers,
                                    files={"manifest_client": buffer.getvalue()})
        if get_files_r.status_code != 200:
            raise GetFileUpdateError(get_files_r.text)
    except:
        logger.error(traceback.format_exc())
        sys.exit(1)

    process_id = get_files_r.json().get("id")

    try:
        # 2. upload files
        # get the file list to upload
        if not get_files_r.json().get("exist"):
            print("The course {} will be newly added".format(os.environ['PLUGIN_COURSE']))
            files_upload = [(static_dir, os.path.getsize(static_dir))]
        else:
            print("The course {} already exists, will be updated".format(os.environ['PLUGIN_COURSE']))
            files_new = get_files_r.json().get("files_new")
            files_update = get_files_r.json().get("files_update")

            files_upload_dict = {**files_new, **files_update}
            files_upload = list()
            for f in list(files_upload_dict.keys()):
                full_path = os.path.join(static_dir, f)
                file_size = os.path.getsize(full_path)
                files_upload.append((full_path, file_size))

        # send request
        data = {"index_mtime": index_mtime, "id": process_id}
        upload_to_server(files_upload, static_dir, upload_url, data)

        # 3. finalize the uploading process
        data = {"index_mtime": index_mtime,
                "upload": "success",
                "id": process_id}
        headers["Content-Type"] = "application/json"
        finalizer_r = requests.get(finalizer_url, headers=headers, json=data)
        print(finalizer_r.text)
    except:
        # Send a signal to the server that the process is aborted
        logger.error(traceback.format_exc())
        data = {"index_mtime": index_mtime,
                "upload": "fail",
                "id": process_id}
        headers["Content-Type"] = "application/json"
        finalizer_r = requests.get(finalizer_url, headers=headers, json=data)
        print(finalizer_r.text)

        sys.exit(1)


if __name__ == "__main__":
    main()
