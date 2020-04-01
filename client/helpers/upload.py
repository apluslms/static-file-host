import os
from io import BytesIO
import tarfile
import requests
from math import floor
import logging

from .utils import UploadError

logger = logging.getLogger(__name__)


def read_in_chunks(buffer, chunk_size=1024 * 1024.0 * 4):
    """Read a buffer in chunks

    Arguments:
        buffer -- a BytesIO object

    Keyword Arguments:
        chunk_size {float} -- the chunk size of each read (default: {1024*1024*4})
    """
    while True:
        data = buffer.read1(chunk_size)
        if not data:
            break
        yield data


def iter_read_chunks(buffer, chunk_size=1024 * 1024 * 4):
    """a iterator of read_in_chunks function

    Arguments:
        buffer -- a BytesIO object

    Keyword Arguments:
         chunk_size {float} -- the chunk size of each read (default: {1024*1024*4})
    """
    # Ensure it's an iterator and get the first field
    it = iter(read_in_chunks(buffer, chunk_size))
    prev = next(read_in_chunks(buffer, chunk_size))
    for item in it:
        # Lag by one item so I know I'm not at the end
        yield prev, False
        prev = item
    # Last item
    yield prev, True


def tar_filelist_buffer(files, basedir):
    """generate a buffer of a compression file

    :param files: a list of tuples (file_path, file_size)
    :param basedir: str, the base directory of the relative file path
    :return: a BytesIO object
    """
    # Create the in-memory file-like object
    buffer = BytesIO()

    # Create the in-memory file-like object
    with tarfile.open(fileobj=buffer, mode='w:gz') as tf:
        for index, f in enumerate(files):
            # Add the file to the tar file
            # 1. 'add' method
            tf.add(f[0], os.path.relpath(f[0], start=basedir))
            # 2. 'addfile' method
            # tf.addfile(tarfile.TarInfo(file_name),open(f[0],'rb'))

    # Change the stream position to the start
    buffer.seek(0)
    return buffer


def compress_files_upload(file_list, last_file, basedir, buff_size_threshold, upload_url, headers, data):
    """ Compress a list of files and upload.
        If the buffer of the compression file smaller than buff_size_threshold, uploaded.
        Otherwise the file list will be divided as two subsets.
        For each subset repeat the above process

    :param file_list: a list of tuples (file_path, file_size)
    :param last_file: str, the path of the last file in the complete file_list
    :param basedir: str, the base directory of the relative file path
    :param buff_size_threshold: float, the threshold of buffer size to determine division action
    :param upload_url: api url for uploading files
    :param headers: dict, headers of requests
    :param data: dict, data of requests
    """
    if not file_list:
        raise ValueError("The file list is empty!")

    # Generate the buffer of the compression file that contains the files in the file_list
    buffer = tar_filelist_buffer(file_list, basedir)

    buffer.seek(0, os.SEEK_END)
    pos = buffer.tell()
    # print('size of the buffer:', pos)
    # Change the stream position to the start
    buffer.seek(0)

    if pos <= buff_size_threshold or len(file_list) == 1:  # post the buffer
        files = {'file': buffer.getvalue()}
        if file_list[-1][0] == last_file:
            data['last_file'] = True
        else:
            data['last_file'] = False
        try:
            res = requests.post(upload_url, headers=headers, data=data, files=files)
            buffer.close()
        except:
            raise
        if res.status_code != 200:
            raise UploadError(res.text)

    else:  # Divide the file_list as two subsets and call the function for each subset
        file_sublists = [file_list[0:floor(len(file_list) / 2)], file_list[floor(len(file_list) / 2):]]
        for l in file_sublists:
            compress_files_upload(l, last_file, basedir, buff_size_threshold, upload_url, headers, data)


def upload_buffer_by_chunk(buffer, whether_last_file, upload_url, headers, data, file_index):
    chunk_size = 1024 * 1024 * 4
    index = 0
    for chunk, last_chunk in iter_read_chunks(buffer, chunk_size=chunk_size):
        offset = index + len(chunk)
        headers['Content-Type'] = 'server_app/octet-stream'
        headers['Process-ID'] = data['process_id']
        headers['Chunk-Size'] = str(chunk_size)
        headers['Chunk-Index'] = str(index)
        headers['Chunk-Offset'] = str(offset)
        headers['File-Index'] = str(file_index)
        headers['Index-Mtime'] = str(data["index_mtime"])
        if last_chunk:
            headers['Last-Chunk'] = 'True'
        if whether_last_file:
            headers['Last-File'] = 'True'
        index = offset
        try:
            res = requests.post(upload_url, headers=headers, data=chunk)
        except:
            raise
        if res.status_code != 200:
            raise UploadError(res.text)


def upload_to_server(files_and_sizes, basedir, upload_url, data):
    """ 1. the files bigger than 50MB are compressed one by one,
        and the smaller files are collected to fill a quota (50MB) and then compressed
        2. the compression file smaller than 4MB is posted directly, otherwise posted by chunks
    """

    # sub listing the files by their sizes (threshold = 50 MB)
    big_files = list(filter(lambda x: x[1] > 50.0 * (1024 * 1024), files_and_sizes))
    small_files = list(filter(lambda x: x[1] <= 50.0 * (1024 * 1024), files_and_sizes))

    init_headers = {
        'Authorization': 'Bearer {}'.format(os.environ['PLUGIN_TOKEN'])
    }
    # big files are compressed and uploaded one by one
    if big_files:
        for file_index, f in enumerate(big_files):

            headers = init_headers
            if file_index == len(big_files) - 1 and not small_files:
                last_file = True
            else:
                last_file = False

            # Create the in-memory file-like object
            buffer = BytesIO()
            # Compress files
            try:
                with tarfile.open(fileobj=buffer, mode='w:gz') as tf:
                    # Write the file to the in-memory tar
                    tf.add(f[0], os.path.relpath(f[0], start=basedir))
            except:
                raise

            # the current position of the buffer
            buffer.seek(0, os.SEEK_END)
            pos = buffer.tell()
            # print("length of the buffer: ", pos)
            # Change the stream position to the start
            buffer.seek(0)

            if pos <= 4.0 * (1024 * 1024):
                # upload the whole compressed file
                file = {'file': buffer.getvalue()}
                data['last_file'] = last_file
                try:
                    res = requests.post(upload_url, headers=headers, data=data, files=file)
                except:
                    raise
                if res.status_code != 200:
                    raise UploadError(res.text)

            else:   # Upload the compressed file by chunks
                upload_buffer_by_chunk(buffer, last_file, upload_url, init_headers, data, file_index)

            buffer.close()

    # Compress small files as one and post it
    if small_files:
        # Add the JWT token to the request headers for the authentication purpose
        headers = {
            'Authorization': 'Bearer {}'.format(os.environ['PLUGIN_TOKEN'])
        }
        last_file = small_files[-1][0]

        compress_files_upload(small_files, last_file, basedir, 4 * 1024 * 1024, upload_url, headers, data)

