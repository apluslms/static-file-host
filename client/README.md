<!---
**Docker Container for uploading static files of a course to the host server**
---- --->

A Docker container that uploads / updates static files of courses to the host server 
https://github.com/QianqianQ/aplus_static_host_server.


**Usage**

This container calls the API of the host server twice: 
1. Calling the endpoint `/<course_name>/get_files_to_update` to get the list of files to upload
2. Calling the endpoint `/<course_name>/upload` to send the selected files to the host server

A server name (domain name), a JWT token and a course name need to be provided as environment variables when starting the container. 

The JWT token of a course (provided by [shepherd](https://github.com/apluslms/shepherd)) is sent to the API in the headers for authentication. 
It contains the name of the course folder in the `sub` field which is also checked whether the same as the course name provided as the environment variable

The course directory which is built by [roman](https://github.com/apluslms/roman) is mounted
to the `$WORKDIR` in the container, and the static files of the course is under `$WORKDIR/_build/html`.

The files are sent using different strategies based on their size:

files larger than 50MB: 
1. For each file, compressing it in memory
1. If the size of the compression file is equal to or smaller than 4 MB, uploading the file directly
2. Otherwise the file is sent by chunks

files smaller than 50MB: 
1. Compressing all the files in memory 
2. If the buffer of the compression file is equal to or smaller than 4 MB, will be sent to the host server
3. Otherwise the small files will be divided as two sublists 
4. For each sublist continue the above process. 

Providing the correct API server name, a valid JWT token and the course name matching the `sub` field of the JWT token, 
the static files of a course is uploaded/updated to `/srv/static_management/courses/{course_name}` in the host server container.

Example of using the container
```bash
docker run --rm -it --name static_upload --network="host" \
  -w /data/ \
  -v "$(pwd):/data/:ro" \
  -e PLUGIN_API=http://0.0.0.0/ \
  -e PLUGIN_TOKEN=eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJkZWZfY291cnNlIiwiaWF0IjoxNTYyODI4MzA0LCJpc3MiOiJzaGVwaGVyZCJ9.MUkoD27P6qZKKMM5juL0e0pZl8OVH6S17N_ZFzC7D0cwOgbcDaAO3S1BauXzhQOneChPs1KEzUxI2dVF-Od_gpN8_IJEnQnk25XmZYecfdoJ5ST-6YonVmUMzKP7UAcvzCFye7mkX7zJ1ADYtda57IUdyaLSPOWnFBSHX5B4XTzzPdVZu1xkRtb17nhA20SUg9gwCOPD6uLU4ml1aOPHBdiMLKz66inI8txPrRK57Gn33m8lVp0WTOOgLV5MkCIpkgVHBl50EHcQFA5KfPet3FBLjpp2I1yThQe_n1Zc6GdnR0v_nqX0JhmmDMOvJ5rhIHZ7B0hEtFy9rKUWOWfcug \
  -e PLUGIN_COURSE=def_course \
  static_upload
```

