import os
import sys
from io import BytesIO
import tarfile
import requests
from math import floor
from operator import itemgetter


def upload_directory(directory, upload_url, index_mtime=None):
    """ The files bigger than 4M is uploaded one by one, 
        and the smaller files are compressed to around 4M compression files to upload
    
    Arguments:
        directory {str} -- path of the course directory
        upload_url {str} -- url uploading to
        index_mtime {float} -- modification time of the index file (possiblily no need to check)
    """

    files_and_sizes = files_sizes_list(directory)

    # sub listing the files by their size (threshold = 4 MB)
    big_files = list(filter(lambda x: x[1] > 4.0, files_and_sizes))
    small_files = list(filter(lambda x: x[1] <= 4.0, files_and_sizes))
    # small_files = [f for f in files_and_sizes if f not in big_files]

    init_headers = {
        'Authorization': 'Bearer {}'.format(os.environ['PLUGIN_TOKEN'])
    }

    # Post big files one by one
    if big_files:
        for file_index, f in enumerate(big_files):

            headers = init_headers
            last_file = False
            if file_index == len(big_files)-1 and not small_files:
                last_file = True

            if f[1] <= 50.0:  # if the file <= 50MB, post the file object directly
                # the modification time of the index.yaml file
                if index_mtime is not None:
                    data = {'index_mtime': index_mtime}
                else:
                    data = dict() 
                file_name = os.path.relpath(f[0], start=directory)
                data['file_name'] = file_name
                # flag of the last configuration file
                if last_file:
                    data['last_file'] = True
                try:
                    response = requests.post(upload_url, headers=headers, 
                                             data=data, files={'file': open(f[0], 'rb')})
                    if last_file:
                        print(response.text)
                except:
                    raise Exception('Error occurs when uploading a file with 4MB < size < 50MB!')

            else:  # if the file > 50MB, compress it and then post by chunks
                # Create the in-memory file-like object
                buffer = BytesIO()
                # Compress 'yaml' files
                try:
                    with tarfile.open(fileobj=buffer, mode='w:gz') as tf:
                        # Write the file to the in-memory tar
                        file_name = os.path.relpath(f[0], start=directory)
                        tf.add(f[0], file_name)
                except:
                    raise Exception('Error occurs!')

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
                    if index_mtime is not None:
                        headers['Index-Mtime'] = str(index_mtime)
                    if whether_last:
                        headers['Last-Chunk'] = 'True'
                    if last_file:
                        headers['Last-File'] = 'True'
                    index = offset
                    try:
                        response = requests.post(upload_url, headers=headers, data=chunk)
                        if last_file:
                            print(response.text)
                    except:
                        raise Exception('Error occurs when uploading a file bigger than 50 MB!')

                buffer.close()

    # Compress small files as one and post it
    if small_files:
        # Add the JWT token to the request headers for the authentication purpose
        headers = {
                    'Authorization': 'Bearer {}'.format(os.environ['PLUGIN_TOKEN'])
                }
        if index_mtime is not None:
            data = {'index_mtime': index_mtime}
        else:
            data = dict() 
        data['compression_file'] = True
        last_file = small_files[-1][0]  # Record the last file

        compress_files_upload(small_files, last_file, directory, 4*1024*1024, upload_url, headers, data)


def check_static_directory(directory):
    """ Check whether the static directory and the index.html file exist
    :param directory: str, the path of a static directory
    :return: the path of the static directory, the path of the index.html file
             and the modification time of the index.html
    """

    # The path of the subdirectory that contains static files
    static_dir = os.path.join(directory, '_build', 'html')
    index_html = os.path.join(html_dir, 'index.html')
    if not os.path.exists(static_dir):
        raise FileNotFoundError("No '_build/html' directory")
    elif not os.path.isdir(static_dir):
        raise NotADirectoryError("'_build/html' is not a directory")
    elif not os.path.exists(index_html):
        raise FileNotFoundError("No '_build/html/index.yaml' file")

    index_mtime = os.path.getmtime(index_html)

    return static_dir, index_html, index_mtime


def files_sizes_list(directory):
    """ Get a list of tuples of file path and size in a directory, sorted by the file size (largest to smallest)
    """
    all_files = [os.path.join(basedir, filename) for basedir, dirs, files in os.walk(directory) for filename in files]
    # list of tuples of file path and size (MB), e.g., ('/Path/to/the.file', 1.0)
    files_and_sizes = [(path, os.path.getsize(path) / (1024 * 1024.0)) for path in all_files]
    files_and_sizes.sort(key=itemgetter(1), reverse=True)

    return files_and_sizes


def read_in_chunks(buffer, chunk_size=1024*1024.0*4):
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


def iter_read_chunks(buffer, chunk_size=1024*1024*4):
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


def tar_filelist_buffer(files, rel_path_start):
    """generate a buffer of a compression file

    :param files: a list of tuples (file_path, file_size)
    :param rel_path_start: str, the start path for relative path of files
    :return: a BytesIO object
    """
    # Create the in-memory file-like object
    buffer = BytesIO()
    
    # Create the in-memory file-like object
    with tarfile.open(fileobj=buffer, mode='w:gz') as tf:
        for index, f in enumerate(files):
            file_name = os.path.relpath(f[0], start=rel_path_start)
            # Add the file to the tar file
            # 1. 'add' method
            tf.add(f[0], file_name)
            # 2. 'addfile' method
            # tf.addfile(tarfile.TarInfo(file_name),open(f[0],'rb'))

    # Change the stream position to the start
    buffer.seek(0)
    return buffer


def compress_files_upload(file_list, last_file, rel_path_start, buff_size_threshold, upload_url, headers, data):
    """ Compress a list of files and upload.
        If the buffer of the compression file smaller than buff_size_threshold, uploaded.
        Otherwise the file list will be divided as two subsets.
        For each subset repeat the above process

    :param file_list: a list of tuples (file_path, file_size)
    :param last_file: tuples (file_path, file_size), the last file of the complete file list
    :param rel_path_start: str, the start path for relative path of files
    :param buff_size_threshold: float, the threshold of buffer size to determine division action
    :param upload_url: api url for uploading files
    :param headers: dict, headers of requests
    :param data: dict, data of requests
    """
    # Generate the buffer of the compression file that contains the files in the file_list
    buffer = tar_filelist_buffer(file_list, rel_path_start)

    if len(buffer.getbuffer()) <= buff_size_threshold or len(file_list) == 1:  # post the buffer
        files = {'file': buffer.getvalue()}
        if file_list[-1][0] == last_file:
            data['last_file'] = True
        try:
            response = requests.post(upload_url, headers=headers, data=data, files=files)
            if 'last_file' in data:
                print(response.text)
        except Exception as e:
            print('Error occurs when uploading a compression file!')
            raise Exception('Error occurs when uploading a compression file!')
        buffer.close()

    else:  # Divide the file_list as two subsets and call the function for each subset
        file_sublists = [file_list[0:floor(len(file_list)/2)], file_list[floor(len(file_list)/2):]]
        for l in file_sublists:
            compress_files_upload(l, last_file, rel_path_start, buff_size_threshold, headers, data)


def error_print():
    return '{}. {}, line: {}'.format(sys.exc_info()[0],
                                     sys.exc_info()[1],
                                     sys.exc_info()[2].tb_lineno)
