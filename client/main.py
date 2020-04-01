import os
import sys
import requests
import argparse
from io import BytesIO
import json
import pprint
import logging
import traceback
#sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'helpers'))
from helpers.upload import upload_to_server
from helpers.utils import (get_file_manifest,
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

COURSE_FOLDER = os.getcwd()
PROCESS_FILE = os.path.join(COURSE_FOLDER, "process_id.json")


def main():

    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--upload', dest='upload', action='store_true', default=False,
                        help='upload the selected files to the server')
    action.add_argument('--publish', dest='publish', action='store_true', default=False,
                        help='publish the selected files to the server')
    parser.add_argument('--file', '-f', dest='file', type=str, required=True,
                        help='The files to select')

    try:
        args = parser.parse_args()
        upload = args.upload
        publish = args.publish
        file = args.file
        print(args)
    except:
        # parser.print_help()
        logger.debug(error_print)
        logger.debug("Invalid args provided")
        sys.exit(1)
    # examine the environment variables
    examine_env_var()
    
    # get the manifest
    target_dir, index_file, index_mtime = check_directory(COURSE_FOLDER, file)
    manifest_client = get_file_manifest(target_dir)

    # Create the in-memory file-like object storing the manifest
    buffer = BytesIO()
    buffer.write(json.dumps(manifest_client).encode('utf-8'))
    buffer.seek(0)

    headers = {
        'Authorization': 'Bearer {}'.format(os.environ['PLUGIN_TOKEN'])
    }
    # upload
    if upload:

        get_files_url = os.environ['PLUGIN_API'] + os.environ['PLUGIN_COURSE'] + '/get-files-to-update'
        upload_url = os.environ['PLUGIN_API'] + os.environ['PLUGIN_COURSE'] + '/upload-file'

        # 1. get the file list to upload from the server side
        try:
            get_files_r = requests.post(get_files_url, headers=headers,
                                        files={"manifest_client": buffer.getvalue()})
            print(get_files_r)
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
        with open(PROCESS_FILE, 'w') as f:
            json.dump({'process_id': process_id}, f)

        try:
            # 2. upload files
            data = {"index_mtime": index_mtime, "process_id": process_id}
            upload_to_server(files_upload, target_dir, upload_url, data)
        except:
            print(error_print())
            sys.exit(1)

    # publish
    elif publish:
        finalizer_url = os.environ['PLUGIN_API'] + os.environ['PLUGIN_COURSE'] + '/upload-finalizer'
        try:
            # 3. finalize the uploading process
            with open(PROCESS_FILE, 'r') as f:
                process_id = json.load(f)['process_id']
            data = {"index_mtime": index_mtime,
                    # "upload": "success",
                    "process_id": process_id}
            headers["Content-Type"] = "application/json"
            try:
                os.remove(PROCESS_FILE)
            except:
                pass
            finalizer_r = requests.get(finalizer_url, headers=headers, json=data)
            if finalizer_r.status_code != 200:
                raise PublishError(finalizer_r.text)
        except:
            print(error_print())
            sys.exit(1)
    else:
        print("Invalid action")
        os.remove(PROCESS_FILE)
        sys.exit(1)


if __name__ == "__main__":
    main()
