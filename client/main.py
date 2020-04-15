import os
import sys
import argparse
import pprint
import logging

from aplus_file_management.client import client_action_upload, client_action_publish

from helpers.utils import (validate_directory,
                           examine_env_var,
                           error_print,
                           )
from helpers import COURSE_FOLDER, PROCESS_FILE, FILE_TYPE1

logger = logging.getLogger(__name__)
pp = pprint.PrettyPrinter(indent=4)

os.environ['PLUGIN_API'] = 'http://0.0.0.0:5000/'
os.environ['PLUGIN_TOKEN'] = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJkZWZfY291cnNlIiwiaWF0IjoxNTYyODI4MzA0LCJpc3MiOiJzaGVwaGVyZCJ9.MUkoD27P6qZKKMM5juL0e0pZl8OVH6S17N_ZFzC7D0cwOgbcDaAO3S1BauXzhQOneChPs1KEzUxI2dVF-Od_gpN8_IJEnQnk25XmZYecfdoJ5ST-6YonVmUMzKP7UAcvzCFye7mkX7zJ1ADYtda57IUdyaLSPOWnFBSHX5B4XTzzPdVZu1xkRtb17nhA20SUg9gwCOPD6uLU4ml1aOPHBdiMLKz66inI8txPrRK57Gn33m8lVp0WTOOgLV5MkCIpkgVHBl50EHcQFA5KfPet3FBLjpp2I1yThQe_n1Zc6GdnR0v_nqX0JhmmDMOvJ5rhIHZ7B0hEtFy9rKUWOWfcug'
os.environ['PLUGIN_COURSE'] = 'def_course'
COURSE_FOLDER = '/u/71/qinq1/unix/Desktop/my_new_course'


def main():

    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--upload', dest='upload', action='store_true', default=False,
                        help='upload the selected files to the server')
    action.add_argument('--publish', dest='publish', action='store_true', default=False,
                        help='publish the selected files to the server')
    parser.add_argument('--file', '-f', dest='file_type', type=str, required=True,
                        help='The files to select')

    try:
        args = parser.parse_args()
        upload = args.upload
        publish = args.publish
        file_type = args.file_type
    except:
        # parser.print_help()
        logger.debug(error_print)
        logger.debug("Invalid args provided")
        sys.exit(1)
    # examine the environment variables
    examine_env_var()
    
    # get the manifest
    data = validate_directory(COURSE_FOLDER, file_type)
    if file_type in FILE_TYPE1:
        target_dir = data['target_dir']
    else:
        raise NotImplementedError
    print(target_dir)

    headers = {
        'Authorization': 'Bearer {}'.format(os.environ['PLUGIN_TOKEN'])
    }
    # upload
    if upload:

        get_files_url = os.environ['PLUGIN_API'] + os.environ['PLUGIN_COURSE'] + '/get-files-to-update'
        upload_url = os.environ['PLUGIN_API'] + os.environ['PLUGIN_COURSE'] + '/upload-file'

        # 1. get the file list to upload from the server side
        client_action_upload(get_files_url, upload_url, headers, target_dir, PROCESS_FILE)

    # publish
    elif publish:
        publish_url = os.environ['PLUGIN_API'] + os.environ['PLUGIN_COURSE'] + '/upload-finalizer'
        client_action_publish(publish_url, headers, PROCESS_FILE)


if __name__ == "__main__":
    main()
