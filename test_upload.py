import pytest
import unittest
import os
import json
import requests
import pprint
from io import BytesIO

from manifest import get_file_manifest, files_to_update_1, files_to_update_2
from upload import upload_files
from utils import check_static_directory

pp = pprint.PrettyPrinter()

uri = 'http://0.0.0.0/'
token = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJkZWZfY291cnNlIiwiaWF0IjoxNTYyODI4MzA0LCJpc3MiOiJzaGVwaGVyZCJ9.MUkoD27P6qZKKMM5juL0e0pZl8OVH6S17N_ZFzC7D0cwOgbcDaAO3S1BauXzhQOneChPs1KEzUxI2dVF-Od_gpN8_IJEnQnk25XmZYecfdoJ5ST-6YonVmUMzKP7UAcvzCFye7mkX7zJ1ADYtda57IUdyaLSPOWnFBSHX5B4XTzzPdVZu1xkRtb17nhA20SUg9gwCOPD6uLU4ml1aOPHBdiMLKz66inI8txPrRK57Gn33m8lVp0WTOOgLV5MkCIpkgVHBl50EHcQFA5KfPet3FBLjpp2I1yThQe_n1Zc6GdnR0v_nqX0JhmmDMOvJ5rhIHZ7B0hEtFy9rKUWOWfcug'
course = 'def_course'
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
    os.environ['PLUGIN_API'] = uri
    os.environ['PLUGIN_TOKEN'] = token
    os.environ['PLUGIN_COURSE'] = course
    examine_env_var()


@pytest.fixture(scope='class')
def test_data(request):
    data = dict()
    data['path'] = {'files_to_update': '/get_files_to_update',
                    'upload': '/upload'}
    data['course_dir'] = course_dir
    data['invalid_headers'] = {
            'no_authorization': {},
            'invalid_scheme': {'Authorization': 'Basic {}'.format(os.environ['PLUGIN_TOKEN'])},
            'invalid_token': {'Authorization': 'Bearer {}'.format('token')}
            }
    data['headers'] = {'Authorization': 'Bearer {}'.format(os.environ['PLUGIN_TOKEN'])}
    request.cls.test_data = data
    yield


@pytest.mark.usefixtures('test_data')
class TestCourseUpload(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        examine_env_var()

    def test_server_setup(self):
        res = requests.get(os.environ['PLUGIN_API'])
        assert res.status_code == 200
        assert res.text == "Static File Management Server"

    def test_auth(self):
        test_url = os.environ['PLUGIN_API'] + os.environ['PLUGIN_COURSE'] + self.test_data['path']['files_to_update']

        # no headers
        res1 = requests.post(test_url)
        # no authorization headers
        res2 = requests.post(test_url, headers=self.test_data['invalid_headers']['no_authorization'])
        # invalid scheme
        res3 = requests.post(test_url, headers=self.test_data['invalid_headers']['invalid_scheme'])
        # invalid token
        res4 = requests.post(test_url, headers=self.test_data['invalid_headers']['invalid_token'])
        # valid token ( no data sent)
        res5 = requests.post(test_url, headers=self.test_data['headers'])

        assert res1.status_code == 401
        assert res2.status_code == 401
        assert res3.status_code == 401
        assert res4.status_code == 401
        assert res5.status_code != 401

    def test_static_dir_access(self):

        # Test the error raised if the dir is not a course dir
        with pytest.raises(FileNotFoundError):
            check_static_directory(os.getcwd())

        # Test the access to a course dir
        check_static_directory(course_dir)

    def test_get_files_to_update(self):
        static_dir, index_html, index_mtime = check_static_directory(self.test_data['course_dir'])
        manifest_client = get_file_manifest(static_dir, os.environ['PLUGIN_COURSE'])
        print("manifests in the client side:")
        pp.pprint(manifest_client)

        url = (os.environ['PLUGIN_API']
               + os.environ['PLUGIN_COURSE']
               + self.test_data['path']['files_to_update'])

        # Create the in-memory file-like object
        buffer = BytesIO()
        buffer.write(json.dumps(manifest_client).encode('utf-8'))
        buffer.seek(0)

        res = requests.post(url, headers=self.test_data['headers'],
                            files={"manifest_client": buffer.getvalue()})

        print(res.text)

        assert res.status_code == 200

    # def test_first_upload(self):
    #
    #     static_dir, index_html, index_mtime = check_static_directory(self.test_data['course_dir'])
    #     manifest_client = get_file_manifest(static_dir, os.environ['PLUGIN_COURSE'])
    #
    #     get_files_url = (os.environ['PLUGIN_API']
    #                      + os.environ['PLUGIN_COURSE']
    #                      + self.test_data['path']['files_to_update'])
    #
    #     # Create the in-memory file-like object
    #     buffer = BytesIO()
    #     buffer.write(json.dumps(manifest_client).encode('utf-8'))
    #     # json.dump(manifest_client, buffer)
    #
    #     # get the manifest of files in the server side
    #     get_files_r = requests.post(get_files_url, headers=self.test_data['headers'],
    #                                 files={"manifest_client": buffer})
    #     assert get_files_r.status_code == 200
    #
    #     upload_url = (os.environ['PLUGIN_API']
    #                   + os.environ['PLUGIN_COURSE']
    #                   + '/upload')
    #     files_upload = [(static_dir, os.path.getsize(static_dir))]
    #     upload_files(files_upload, static_dir, upload_url, index_mtime)

    # def test_upload_after_first_time(self):

        # not a newer version (compare with that in the remote server)
        # a newer version

    # def test_upload_small_files(self):
    # def_test_large_files(self):



