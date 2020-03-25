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
                   check_directory,
                   examine_env_var,
                   GetFileUpdateError,
                   PublishError,
                   error_print,
                   )

logger = logging.getLogger(__name__)
pp = pprint.PrettyPrinter(indent=4)

# os.environ['PLUGIN_API'] = 'http://0.0.0.0:5000/'
# os.environ['PLUGIN_TOKEN'] = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJkZWZfY291cnNlIiwiaWF0IjoxNTYyODI4MzA0LCJpc3MiOiJzaGVwaGVyZCJ9.MUkoD27P6qZKKMM5juL0e0pZl8OVH6S17N_ZFzC7D0cwOgbcDaAO3S1BauXzhQOneChPs1KEzUxI2dVF-Od_gpN8_IJEnQnk25XmZYecfdoJ5ST-6YonVmUMzKP7UAcvzCFye7mkX7zJ1ADYtda57IUdyaLSPOWnFBSHX5B4XTzzPdVZu1xkRtb17nhA20SUg9gwCOPD6uLU4ml1aOPHBdiMLKz66inI8txPrRK57Gn33m8lVp0WTOOgLV5MkCIpkgVHBl50EHcQFA5KfPet3FBLjpp2I1yThQe_n1Zc6GdnR0v_nqX0JhmmDMOvJ5rhIHZ7B0hEtFy9rKUWOWfcug'
# os.environ['PLUGIN_COURSE'] = 'def_course'
# os.environ['UPLOAD_FILE'] = 'html'
# course_dir = '/u/71/qinq1/unix/Desktop/my_new_course'


def main():

    # examine the environment variables
    examine_env_var()
    
    # get the manifest
    course_dir = os.getcwd()
    target_dir, index_file, index_mtime = check_directory(course_dir, os.environ['UPLOAD_FILE'])
    manifest_client = get_file_manifest(target_dir)

    # Create the in-memory file-like object storing the manifest
    buffer = BytesIO()
    buffer.write(json.dumps(manifest_client).encode('utf-8'))
    buffer.seek(0)

    headers = {
        'Authorization': 'Bearer {}'.format(os.environ['PLUGIN_TOKEN'])
    }

    # upload
    if os.environ['ACTION'] == 'upload':

        get_files_url = os.environ['PLUGIN_API'] + os.environ['PLUGIN_COURSE'] + '/get-files-to-update'
        upload_url = os.environ['PLUGIN_API'] + os.environ['PLUGIN_COURSE'] + '/upload-file'

        # 1. get the file list to upload from the server side
        try:
            get_files_r = requests.post(get_files_url, headers=headers,
                                        files={"manifest_client": buffer.getvalue()})
            if get_files_r.status_code != 200:
                raise GetFileUpdateError(get_files_r.text)

            if not get_files_r.json().get("exist"):
                print("The course {} will be newly added".format(os.environ['PLUGIN_COURSE']))
                files_upload = [(target_dir, os.path.getsize(target_dir))]
            else:
                print("The course {} already exists, will be updated".format(os.environ['PLUGIN_COURSE']))
                files_new = get_files_r.json().get("files_new")
                files_update = get_files_r.json().get("files_update")

                files_upload_dict = {**files_new, **files_update}
                files_upload = list()
                for f in list(files_upload_dict.keys()):
                    full_path = os.path.join(target_dir, f)
                    file_size = os.path.getsize(full_path)
                    files_upload.append((full_path, file_size))
        except:
            logger.error(traceback.format_exc())
            sys.exit(1)

        # store the id of this process
        process_id = get_files_r.json().get("process_id")
        with open(os.path.join(course_dir, 'process_id.json'), 'w') as f:
            json.dump({'process_id': process_id}, f)

        try:
            # 2. upload files
            data = {"index_mtime": index_mtime, "process_id": process_id}
            upload_to_server(files_upload, target_dir, upload_url, data)

            # 3. finalize the uploading process
            # data = {"index_mtime": index_mtime,
            #         "upload": "success",
            #         "id": process_id}
            # headers["Content-Type"] = "application/json"
            # finalizer_r = requests.get(finalizer_url, headers=headers, json=data)
            # print(finalizer_r.text)
        except:
            # Send a signal to the server that the process is aborted
            # logger.error(traceback.format_exc())
            # data = {"index_mtime": index_mtime,
            #         "upload": "fail",
            #         "id": process_id}
            # headers["Content-Type"] = "application/json"
            # finalizer_r = requests.get(finalizer_url, headers=headers, json=data)
            # print(finalizer_r.text)
            print(error_print())
            sys.exit(1)

    # publish
    elif os.environ['ACTION'] == 'publish':
        finalizer_url = os.environ['PLUGIN_API'] + os.environ['PLUGIN_COURSE'] + '/upload-finalizer'
        try:
            # 3. finalize the uploading process
            with open(os.path.join(course_dir, 'process_id.json'), 'r') as f:
                process_id = json.load(f)['process_id']
            data = {"index_mtime": index_mtime,
                    # "upload": "success",
                    "process_id": process_id}
            headers["Content-Type"] = "application/json"
            os.remove(os.path.join(course_dir, 'process_id.json'))
            finalizer_r = requests.get(finalizer_url, headers=headers, json=data)
            if finalizer_r.status_code != 200:
                raise PublishError(finalizer_r.text)
        except:
            print(error_print())
            sys.exit(1)
    else:
        print("Invalid action")
        os.remove(os.path.join(course_dir, 'process_id.json'))
        sys.exit(1)


if __name__ == "__main__":
    main()
