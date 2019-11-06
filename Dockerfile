FROM apluslms/service-base:python3-1.5
 
RUN pip3 install requests
ADD main.py /bin/
ADD utils.py /bin/

ENTRYPOINT ["python3", "/bin/main.py"]
