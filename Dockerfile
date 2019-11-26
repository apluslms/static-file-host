FROM apluslms/service-base:python3-1.5

COPY main.py utils.py requirements.txt  /bin/
RUN pip3 install -r  /bin/requirements.txt

ENTRYPOINT ["python3", "/bin/main.py"]
