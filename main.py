import os
import requests
from io import BytesIO
import json

from manifest import get_file_manifest, files_to_update_1, files_to_update_2
from upload import upload_files
from utils import check_static_directory, error_print


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
            print("The course will be newly added")
            file_upload = [(static_dir, os.path.getsize(static_dir))]
            upload_files(file_upload, static_dir, upload_url, index_mtime)
        else:
            print("The course already exists")
            manifest_srv = manifest_r.json().get("manifest_srv")

            # file_upload, file_remove = files_to_update_1(manifest_client, manifest_srv, static_dir)
            # print("upload {} files, delete {] files".format(len(file_upload), len(file_remove)))
            # print(dict(filter(lambda i: i[0] in file_remove, manifest_srv.items())))

            file_upload = files_to_update_2(manifest_client, manifest_srv, static_dir)
            print("upload {} files".format(len(file_upload)))

            upload_files(file_upload, static_dir, upload_url, index_mtime)
    except:
        return requests.HTTPError(error_print())


if __name__ == "__main__":
    main()
