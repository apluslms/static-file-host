import os
from utils import upload_directory, check_static_directory


def main():

    if 'PLUGIN_API' in os.environ and 'PLUGIN_TOKEN' in os.environ and 'PLUGIN_COURSE' in os.environ:
        upload_url = os.environ['PLUGIN_API'] + os.environ['PLUGIN_COURSE'] + '/upload'
        
        static_dir, index_html, index_mtime = check_static_directory(os.getcwd())

        upload_directory(static_dir, upload_url, index_mtime)
    else:
        raise ValueError('No API or JWT token provided')


if __name__ == "__main__":
    main()
