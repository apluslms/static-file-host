FROM apluslms/service-base:python3-1.5
#FROM tiangolo/uwsgi-nginx-flask:python3.7

ENV DEBIAN_FRONTEND noninteractive
ENV SERVER_PATH /srv/static_management

#ENV LISTEN_PORT 5000
#ENV NGINX_WORKER_PROCESSES auto
#ENV NGINX_WORKER_CONNECTIONS 1024
#ENV NGINX_WORKER_OPEN_FILES 1024
#
#ENV UWSGI_CHEAPER 50
#ENV UWSGI_PROCESSES 51

COPY . ${SERVER_PATH}
WORKDIR ${SERVER_PATH}

RUN :\
    && apt-get update \
    && apt-get install -y \
        build-essential \
        python3-dev \
#        uwsgi-plugin-python3 \
        nginx\
        libpcre3 \
        libpcre3-dev \
#    && adduser --system --disabled-password --gecos "static management server,,," --ingroup www-data static_management \
    && chown -R www-data:www-data /srv/static_management \
    && pip3 install -r requirements.txt \
    && pip3 install uwsgi -I --no-cache-dir

#EXPOSE 5000
#CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]
#CMD ["uwsgi", "--socket", "0.0.0.0:5000", "--protocol=http", "-w", "static_management"]
CMD ["uwsgi","app.ini"]
