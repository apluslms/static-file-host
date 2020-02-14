FROM apluslms/service-base:python3-1.5

ENV TZ=Europe/Helsinki

COPY requirements.txt utils.py upload.py main.py /bin/
RUN pip3 install -r  /bin/requirements.txt
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone


ENTRYPOINT ["python3", "/bin/main.py"]
