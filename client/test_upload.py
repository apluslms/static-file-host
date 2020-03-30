import pytest
import unittest
import pytest_check as check

import os
import json
import requests
import pprint
import subprocess
import tarfile
import traceback
import logging
from io import BytesIO

from upload import upload_files, compress_files_upload, iter_read_chunks
from utils import (get_file_manifest,
                   check_static_directory,
                   EnvVarNotFoundError,
                   examine_env_var,
                   UploadError,
                   )


logger = logging.getLogger(__name__)
pp = pprint.PrettyPrinter()

uri = 'http://0.0.0.0/'
token = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJkZWZfY291cnNlIiwiaWF0IjoxNTYyODI4MzA0LCJpc3MiOiJzaGVwaGVyZCJ9.MUkoD27P6qZKKMM5juL0e0pZl8OVH6S17N_ZFzC7D0cwOgbcDaAO3S1BauXzhQOneChPs1KEzUxI2dVF-Od_gpN8_IJEnQnk25XmZYecfdoJ5ST-6YonVmUMzKP7UAcvzCFye7mkX7zJ1ADYtda57IUdyaLSPOWnFBSHX5B4XTzzPdVZu1xkRtb17nhA20SUg9gwCOPD6uLU4ml1aOPHBdiMLKz66inI8txPrRK57Gn33m8lVp0WTOOgLV5MkCIpkgVHBl50EHcQFA5KfPet3FBLjpp2I1yThQe_n1Zc6GdnR0v_nqX0JhmmDMOvJ5rhIHZ7B0hEtFy9rKUWOWfcug'
course = 'def_course'
course_dir = '/u/71/qinq1/unix/Desktop/my_new_course'


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
    # data['path'] = {'files_to_update': '/get_files_to_update',
    #                 'upload': '/upload'}
    data['course_dir'] = course_dir
    data['invalid_headers'] = {
            'no_authorization': {},
            'invalid_scheme': {'Authorization': 'Basic {}'.format(os.environ['PLUGIN_TOKEN'])},
            'invalid_token': {'Authorization': 'Bearer {}'.format('token')}
            }
    data['headers'] = {'Authorization': 'Bearer {}'.format(os.environ['PLUGIN_TOKEN'])}
    data['get_files_url'] = (os.environ['PLUGIN_API']
                             + os.environ['PLUGIN_COURSE']
                             + '/get_files_to_update')
    data['upload_url'] = (os.environ['PLUGIN_API']
                          + os.environ['PLUGIN_COURSE']
                          + '/upload')
    request.cls.test_data = data
    yield


@pytest.fixture(scope='session', autouse=True)
def test_log(request):
    logging.info("Test '{}' STARTED".format(request.node.nodeid))

    def fin():
        logging.info("Test '{}' COMPLETED".format(request.node.nodeid))
    request.addfinalizer(fin)


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
        test_url = self.test_data['get_files_url']

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

        check.equal(res1.status_code, 401)
        check.equal(res2.status_code, 401)
        check.equal(res3.status_code, 401)
        check.equal(res4.status_code, 401)
        check.not_equal(res5.status_code, 401)

    def test_static_dir_access(self):

        # Test the error raised if the dir is not a course dir
        with pytest.raises(FileNotFoundError):
            check_static_directory(os.getcwd())

        # Test the access to a course dir
        check_static_directory(course_dir)

    def get_files_to_update(self):
        static_dir, index_html, index_mtime = check_static_directory(self.test_data['course_dir'])
        manifest_client = get_file_manifest(static_dir, os.environ['PLUGIN_COURSE'])
        # print("manifests in the client side:")
        # pp.pprint(manifest_client)

        # Create the in-memory file-like object
        buffer = BytesIO()
        buffer.write(json.dumps(manifest_client).encode('utf-8'))
        buffer.seek(0)

        res = requests.post(self.test_data['get_files_url'], headers=self.test_data['headers'],
                            files={"manifest_client": buffer.getvalue()})

        return res, manifest_client

    def test_first_upload(self):
        get_files_r, manifest_client = self.get_files_to_update()
        assert get_files_r.status_code == 200
        assert get_files_r.json().get("exist") is False
        assert get_files_r.json().get("course_instance") == "def_course"

        static_dir, index_html, index_mtime = check_static_directory(self.test_data['course_dir'])
        files_upload = [(static_dir, os.path.getsize(static_dir))]
        upload_files(files_upload, static_dir, self.test_data['upload_url'], index_mtime)

    def test_upload(self):

        # not a newer version (compare with that in the remote server)
        get_files_r, manifest_client = self.get_files_to_update()
        if get_files_r.status_code == 200:
            assert get_files_r.json().get("course_instance") == "def_course"
            assert get_files_r.json().get("exist") is not None

            static_dir, index_html, index_mtime = check_static_directory(self.test_data['course_dir'])
            files_upload = [(static_dir, os.path.getsize(static_dir))]
            upload_files(files_upload, static_dir, self.test_data['upload_url'], index_mtime)
        else:
            assert get_files_r.status_code == 400

        # a newer version
        with open(os.devnull, "w") as f:
            subprocess.run("./docker-compile.sh", cwd=course_dir, stdout=f)
        get_files_r, manifest_client = self.get_files_to_update()
        assert get_files_r.status_code == 200
        assert get_files_r.json().get("exist") is True
        assert get_files_r.json().get("course_instance") == "def_course"

        static_dir, index_html, index_mtime = check_static_directory(self.test_data['course_dir'])
        files_new = get_files_r.json().get("files_new")
        files_update = get_files_r.json().get("files_update")
        files_upload_dict = {**files_new, **files_update}
        files_upload = list()
        # for f in files_new + files_update:
        for f in list(files_upload_dict.keys()):
            full_path = os.path.join(static_dir, f.replace(os.environ['PLUGIN_COURSE'] + os.sep, ''))
            file_size = os.path.getsize(full_path)
            files_upload.append((full_path, file_size))
        upload_files(files_upload, static_dir, self.test_data['upload_url'], index_mtime)

    # This test fails if run the former uploading tests
    def test_upload_small_files(self):

        with open(os.devnull, "w") as f:
            subprocess.run("./docker-compile.sh", cwd=course_dir, stdout=f)
        get_files_r, manifest_client = self.get_files_to_update()
        static_dir, index_html, index_mtime = check_static_directory(self.test_data['course_dir'])

        assert get_files_r.status_code == 200

        # pp.pprint(get_files_r.json())

        files_new = get_files_r.json().get("files_new")
        files_update = get_files_r.json().get("files_update")
        files_upload_dict = {**files_new, **files_update}
        files_upload = list()
        # for f in files_new + files_update:
        for f in list(files_upload_dict.keys()):
            full_path = os.path.join(static_dir, f.replace(os.environ['PLUGIN_COURSE'] + os.sep, ''))
            file_size = os.path.getsize(full_path)
            files_upload.append((full_path, file_size))

        data = {'index_mtime': index_mtime}
        compress_files_upload(files_upload, files_upload[-1][0], static_dir, 4 * 1024 * 1024,
                              self.test_data['upload_url'], self.test_data['headers'], data)

    # This test fails if run the former uploading tests
    def test_upload_big_files_by_compressed(self):

        with open(os.devnull, "w") as f:
            subprocess.run("./docker-compile.sh", cwd=course_dir, stdout=f)
        get_files_r, manifest_client = self.get_files_to_update()
        static_dir, index_html, index_mtime = check_static_directory(self.test_data['course_dir'])
        assert get_files_r.status_code == 200
        # pp.pprint(get_files_r.json())

        files_new = get_files_r.json().get("files_new")
        files_update = get_files_r.json().get("files_update")
        files_upload_dict = {**files_new, **files_update}
        files_upload = list()

        for f in list(files_upload_dict.keys()):
            full_path = os.path.join(static_dir, f.replace(os.environ['PLUGIN_COURSE'] + os.sep, ''))
            file_size = os.path.getsize(full_path)
            files_upload.append((full_path, file_size))

        for file_index, f in enumerate(files_upload):

            headers = self.test_data['headers']
            if file_index == len(files_upload) - 1:
                last_file = True
            else:
                last_file = False

            # Create the in-memory file-like object'
            buffer = BytesIO()
            # Compress files
            try:
                with tarfile.open(fileobj=buffer, mode='w:gz') as tf:
                    # Write the file to the in-memory tar
                    tf.add(f[0], os.path.relpath(f[0], start=static_dir))
            except:
                print(traceback.format_exc())
                raise

            # Change the stream position to the start
            buffer.seek(0)
            # Upload the compressed file by chunks

            # upload the whole compressed file
            file = {'file': buffer.getvalue()}
            data = {'last_file': last_file}
            try:
                response = requests.post(self.test_data['upload_url'], headers=headers, data=data, files=file)
                assert response.status_code == 200
                if response.json().get('status') == 'finish':
                    print(response.text)
            except:
                print(traceback.format_exc())
                break

            buffer.close()

    def test_upload_big_files_by_chunks(self):

        with open(os.devnull, "w") as f:
            subprocess.run("./docker-compile.sh", cwd=course_dir, stdout=f)
        get_files_r, manifest_client = self.get_files_to_update()
        static_dir, index_html, index_mtime = check_static_directory(self.test_data['course_dir'])
        files_new = get_files_r.json().get("files_new")
        files_update = get_files_r.json().get("files_update")
        files_upload_dict = {**files_new, **files_update}
        files_upload = list()
        # for f in files_new + files_update:
        for f in list(files_upload_dict.keys()):
            full_path = os.path.join(static_dir, f.replace(os.environ['PLUGIN_COURSE'] + os.sep, ''))
            file_size = os.path.getsize(full_path)
            files_upload.append((full_path, file_size))

        for file_index, f in enumerate(files_upload):

            headers = self.test_data['headers']
            if file_index == len(files_upload) - 1:
                last_file = True
            else:
                last_file = False

            # Create the in-memory file-like object'
            buffer = BytesIO()
            # Compress files
            try:
                with tarfile.open(fileobj=buffer, mode='w:gz') as tf:
                    # Write the file to the in-memory tar
                    tf.add(f[0], os.path.relpath(f[0], start=static_dir))
            except:
                print(traceback.format_exc())
                raise

            # Change the stream position to the start
            buffer.seek(0)

            # Upload the compressed file by chunks
            chunk_size = 1024 * 1024 * 4
            index = 0
            for chunk, whether_last in iter_read_chunks(buffer, chunk_size=chunk_size):
                offset = index + len(chunk)
                headers['Content-Type'] = 'application/octet-stream'
                headers['Chunk-Size'] = str(chunk_size)
                headers['Chunk-Index'] = str(index)
                headers['Chunk-Offset'] = str(offset)
                headers['File-Index'] = str(file_index)
                headers['Index-Mtime'] = str(index_mtime)
                if whether_last:
                    headers['Last-Chunk'] = 'True'
                if last_file:
                    headers['Last-File'] = 'True'
                index = offset
                try:
                    response = requests.post(self.test_data['upload_url'], headers=headers, data=chunk)
                    assert response.status_code == 200
                    if response.json().get('status') == 'finish':
                        print(response.text)
                except:
                    raise

            buffer.close()

