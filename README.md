**Static File Host**
----
The static file host server hosting the static files of courses. 
It provides an API allowing users to upload/update static files of courses to it.
 
  
* **Authentication**

  It applies JWT authentication with RS256 algorithm. A JWT token is encoded 
  by a private key in the service [shepherd](https://github.com/apluslms/shepherd).
  The token is sent in the Authorization header when making requests to the API, 
  and this server provides a public key in PEM format to decode and authenticate it. 
  
  An example of a public key:
    ```bash
    JWT_PUBLIC_KEY = """
    -----BEGIN PUBLIC KEY-----
    MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0QIB6wP5rGpT7pcKM0uQ
    bn3FbQI2Xp58vLW+eLISgPvh0EMNuVWMazRfTBGnSxYI2P2F+Yf+O8Ck3JWOpuCD
    +i0a+RlC7gZdspULHpRYSccOqvRdcMn93nuPxiHJ+zAFuVR6mmDQmkHR3ruFvbQt
    FWABpbZpqVOlaOUqoyQcp7JGOrrGZZhifS8EE56azvhIm8n2qf+KhKkTq0P71j+4
    3h2sZtHM9nrsm/wtyb26xPBwGS1v1d5bWw0D2vhPSCP4HV2DuI6WD6pEN9Axjf5j
    dG7tGa6GnyPchdDAvlnA1FQiFfkz4NQtL5upmGiz6gBslFlPhZmejlr2RUYd4mbQ
    3QIDAQAB
    -----END PUBLIC KEY-----
    """ 
    ```
   The payload of a JWT token generated by [shepherd](https://github.com/apluslms/shepherd) 
   includes the fields Subject, Issuer and Issued at. 
   The Subject field is the name of the course folder, and the Issuer field is restricted, `JWT_ISSUER = shepherd`. 
   An example of the payload component of a JWT token:
    ```bash
   {
   'sub': 'def_course', 
   'iss': 'shepherd',  
   'iat': 1562828304
   }
    ```
  The client also needs to provide a parameter `course_name` in the url, and whether the `course_name` 
  and the `sub` field are the same will also be checked.
  
* **Method:**
  
  `POST /<course_name>/get-files-to-update` - Get the list of files to upload / update
  
  `POST /<course_name>/upload-file` - Upload files 
  
  `POST /<course_name>/publish-file` - Publish files 
  
  To upload / update static files, first calling the endpoint `/<course_name>/get-files-to-update` 
  to decide which files to upload, and then calling the endpoint `/<course_name>/upload-file` to upload selected files.
  Finally calling `/<course_name>/publish-file` to publish the uploaded files to the server.
  <!---A docker container for using this API can be seen here: 
  https://github.com/QianqianQ/aplus_static_upload_container-->
