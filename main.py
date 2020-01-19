import os
import requests
from io import BytesIO
import json
import pprint

from manifest import get_file_manifest, files_to_update_1, files_to_update_2
from upload import upload_files
from utils import check_static_directory, error_print

pp = pprint.PrettyPrinter(indent=4)


def main():

    if not ({'PLUGIN_API', 'PLUGIN_TOKEN', 'PLUGIN_COURSE'} <= os.environ.keys()):
        raise ValueError('No API or JWT token provided')

    static_dir, index_html, index_mtime = check_static_directory(os.getcwd())
    manifest_client = get_file_manifest(static_dir, os.environ['PLUGIN_COURSE'])
    print("manifests in the client side:")
    print(manifest_client)

    manifest_compare_url = os.environ['PLUGIN_API'] + os.environ['PLUGIN_COURSE'] + '/get_files_to_update'

    # Create the in-memory file-like object
    buffer = BytesIO()
    buffer.write(json.dumps(manifest_client).encode('utf-8'))
    # json.dump(manifest_client, buffer)
    headers = {
        'Authorization': 'Bearer {}'.format(os.environ['PLUGIN_TOKEN'])
    }

    # get the manifest of files in the server side
    compare_r = requests.post(manifest_compare_url, headers=headers,
                              files={"manifest_client": buffer})

    if compare_r.status_code != 200:
        return requests.HTTPError(compare_r.text)

    # try:
    #     if not manifest_r.json().get("exist"):
    #         print("The course will be newly added")
    #         file_upload = [(static_dir, os.path.getsize(static_dir))]
    #         upload_files(file_upload, static_dir, upload_url, index_mtime)
    #     else:
    #         print("The course already exists")
    #         manifest_srv = manifest_r.json().get("manifest_srv")
    #         print("manifest in the server side")
    #         pp.pprint(manifest_srv)
    #
    #         # file_upload, file_remove = files_to_update_1(manifest_client, manifest_srv, static_dir)
    #         # print("upload {} files, delete {] files".format(len(file_upload), len(file_remove)))
    #         # print(dict(filter(lambda i: i[0] in file_remove, manifest_srv.items())))
    #
    #         file_upload = files_to_update_2(manifest_client, manifest_srv, static_dir)
    #         print("upload {} files".format(len(file_upload)))
    #
    #         upload_files(file_upload, static_dir, upload_url, index_mtime)
    # except:
    #     return requests.HTTPError(error_print())

    upload_url = os.environ['PLUGIN_API'] + os.environ['PLUGIN_COURSE'] + '/upload'

    try:
        # json_data = json.loads(compare_r.text)
        if not compare_r.json().get("exist"):
            print("The course will be newly added")
            files_upload = [(static_dir, os.path.getsize(static_dir))]
            upload_files(files_upload, static_dir, upload_url, index_mtime)
        else:
            print("The course already exists, will be updated")
            files_new = compare_r.json().get("files_new")
            files_update = compare_r.json().get("files_update")
            # file_upload, file_remove = files_to_update_1(manifest_client, manifest_srv, static_dir)
            # print("upload {} files, delete {] files".format(len(file_upload), len(file_remove)))
            # print(dict(filter(lambda i: i[0] in file_remove, manifest_srv.items())))
            files_upload_dict = {**files_new, **files_update}
            files_upload = list()
            # for f in files_new + files_update:
            for f in list(files_upload_dict.keys()):
                full_path = os.path.join(static_dir, f.replace(os.environ['PLUGIN_COURSE']+os.sep, ''))
                file_size = os.path.getsize(full_path)
                files_upload.append((full_path, file_size))

            upload_files(files_upload, static_dir, upload_url, index_mtime)
    except:
        # Send a signal to the server that the process is aborted
        # and the temp json file of the manifest should be removed?
        return requests.HTTPError(error_print())


if __name__ == "__main__":
    main()
