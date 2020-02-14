import os
import sys
import requests
from io import BytesIO
import json
import pprint
import logging

from upload import upload_files
from utils import (get_file_manifest,
                   check_static_directory,
                   examine_env_var,
                   error_print,
                   )

logger = logging.getLogger(__name__)
pp = pprint.PrettyPrinter(indent=4)


def main():

    examine_env_var()

    static_dir, index_html, index_mtime = check_static_directory(os.getcwd())
    manifest_client = get_file_manifest(static_dir, os.environ['PLUGIN_COURSE'])
    # print("manifests in the client side:")
    # pp.pprint(manifest_client)

    get_files_url = os.environ['PLUGIN_API'] + os.environ['PLUGIN_COURSE'] + '/get_files_to_update'

    # Create the in-memory file-like object
    buffer = BytesIO()
    buffer.write(json.dumps(manifest_client).encode('utf-8'))
    buffer.seek(0)
    # json.dump(manifest_client, buffer)
    headers = {
        'Authorization': 'Bearer {}'.format(os.environ['PLUGIN_TOKEN'])
    }

    # get the manifest of files in the server side
    try:
        get_files_r = requests.post(get_files_url, headers=headers,
                                    files={"manifest_client": buffer.getvalue()})
    except requests.exceptions.RequestException as e:
        raise e

    if get_files_r.status_code != 200:
        logger.error(get_files_r.text)
        sys.exit(1)

    upload_url = os.environ['PLUGIN_API'] + os.environ['PLUGIN_COURSE'] + '/upload'

    try:
        # json_data = json.loads(get_files_r.text)
        if not get_files_r.json().get("exist"):
            print("The course {} will be newly added".format(os.environ['PLUGIN_COURSE']))
            files_upload = [(static_dir, os.path.getsize(static_dir))]
            upload_files(files_upload, static_dir, upload_url, index_mtime)
        else:
            print("The course {} already exists, will be updated".format(os.environ['PLUGIN_COURSE']))
            files_new = get_files_r.json().get("files_new")
            files_update = get_files_r.json().get("files_update")

            files_upload_dict = {**files_new, **files_update}
            files_upload = list()
            for f in list(files_upload_dict.keys()):
                full_path = os.path.join(static_dir, f.replace(os.environ['PLUGIN_COURSE']+os.sep, ''))
                file_size = os.path.getsize(full_path)
                files_upload.append((full_path, file_size))

            upload_files(files_upload, static_dir, upload_url, index_mtime)
    except:
        # Send a signal to the server that the process is aborted
        # and the temp json file of the manifest should be removed?
        logger.error(error_print())
        sys.exit(1)


if __name__ == "__main__":
    main()
