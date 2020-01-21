import pytest
import unittest
import os
import json
import requests
from io import BytesIO

from manifest import get_file_manifest, files_to_update_1, files_to_update_2
from upload import upload_files
from utils import check_static_directory, error_print

course_dir = '/u/71/qinq1/unix/Desktop/my_new_course'


class EnvVarNotFoundError(Exception):
    def __init__(self, *var_name):
        self.msg = " & ".join(*var_name) + " missing!"

    def __str__(self):
        return repr(self.msg)


def examine_env_var():
    required = {'PLUGIN_API', 'PLUGIN_TOKEN', 'PLUGIN_COURSE'}

    if required <= os.environ.keys():
        pass
    else:
        missing = [var for var in required if var not in os.environ]
        raise EnvVarNotFoundError(missing)


def test_env_var_missing():
    with pytest.raises(EnvVarNotFoundError):
        examine_env_var()


class TestCourseUpload(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ['PLUGIN_API'] = 'http://0.0.0.0/'
        os.environ['PLUGIN_TOKEN'] = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJkZWZfY291cnNlIiwiaWF0IjoxNTYyODI4MzA0LCJpc3MiOiJzaGVwaGVyZCJ9.MUkoD27P6qZKKMM5juL0e0pZl8OVH6S17N_ZFzC7D0cwOgbcDaAO3S1BauXzhQOneChPs1KEzUxI2dVF-Od_gpN8_IJEnQnk25XmZYecfdoJ5ST-6YonVmUMzKP7UAcvzCFye7mkX7zJ1ADYtda57IUdyaLSPOWnFBSHX5B4XTzzPdVZu1xkRtb17nhA20SUg9gwCOPD6uLU4ml1aOPHBdiMLKz66inI8txPrRK57Gn33m8lVp0WTOOgLV5MkCIpkgVHBl50EHcQFA5KfPet3FBLjpp2I1yThQe_n1Zc6GdnR0v_nqX0JhmmDMOvJ5rhIHZ7B0hEtFy9rKUWOWfcug'
        os.environ['PLUGIN_COURSE'] = 'def_course'
        examine_env_var()

    def test_server_setup(self):
        headers = {
            'Authorization': 'Bearer {}'.format(os.environ['PLUGIN_TOKEN'])
        }
        response = requests.get(os.environ['PLUGIN_API'], headers=headers)
        assert response.status_code == 200
        # assert response.text == "Static File Management Server"

    def test_static_dir_access(self):

        # Test the error raised if the dir is not a course dir
        with pytest.raises(FileNotFoundError):
            check_static_directory(os.getcwd())

        # Test the access to a course dir
        check_static_directory(course_dir)

    def test_first_upload(self):
        static_dir, index_html, index_mtime = check_static_directory(course_dir)
        manifest_client = get_file_manifest(static_dir, os.environ['PLUGIN_COURSE'])
        print("manifests in the client side:\n", manifest_client)

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

        assert compare_r.status_code == 200
