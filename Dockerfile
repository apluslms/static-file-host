FROM apluslms/service-base:python3-1.5

ARG UPLOAD_FILE=$1

ENV TZ=Europe/Helsinki
ENV UPLOAD_FILE=${UPLOAD_FILE}

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

COPY requirements.txt /bin/
RUN pip3 install -r  /bin/requirements.txt

COPY  utils.py upload.py main.py /bin/


ENTRYPOINT ["python3", "/bin/main.py"]
#CMD []
