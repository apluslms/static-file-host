import os
import sys
import logging


logger = logging.getLogger(__name__)


def check_static_directory(directory):
    """ Check whether the static directory and the index.html file exist
    :param directory: str, the path of a static directory
    :return: the path of the static directory, the path of the index.html file
             and the modification time of the index.html
    """

    # The path of the subdirectory that contains static files
    static_dir = os.path.join(directory, '_build', 'html')
    index_html = os.path.join(static_dir, 'index.html')
    if not os.path.exists(static_dir):
        raise FileNotFoundError("No '_build/html' directory")
    elif not os.path.isdir(static_dir):
        raise NotADirectoryError("'_build/html' is not a directory")
    elif not os.path.exists(index_html):
        raise FileNotFoundError("No '_build/html/index.yaml' file")

    index_mtime = os.path.getmtime(index_html) * 1e6

    return static_dir, index_html, index_mtime


class UploadError(Exception):
    pass


def error_print():
    return '{}. {}, line: {}'.format(sys.exc_info()[0],
                                     sys.exc_info()[1],
                                     sys.exc_info()[2].tb_lineno)

