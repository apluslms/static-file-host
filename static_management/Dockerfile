FROM apluslms/service-base:python3-1.5
#FROM tiangolo/uwsgi-nginx-flask:python3.7

ENV DEBIAN_FRONTEND noninteractive
ENV SERVER_PATH /srv/static_management
ENV TZ=Europe/Helsinki

COPY . ${SERVER_PATH}
WORKDIR ${SERVER_PATH}

RUN :\
    && apt-get update \
    && apt-get install -y \
        build-essential \
        python3-dev \
        nginx\
        libpcre3 \
        libpcre3-dev \
#    && adduser --system --disabled-password --gecos "static management server,,," --ingroup www-data management \
    && chown -R www-data:www-data /srv/static_management \
    && pip3 install -r requirements.txt \
    && pip3 install uwsgi -I --no-cache-dir \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

CMD ["uwsgi","app.ini"]
