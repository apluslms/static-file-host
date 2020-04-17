FROM apluslms/service-base:python3-1.5

ARG SERVER_FILE

ENV SERVER_FILE=${SERVER_FILE}
ENV DEBIAN_FRONTEND noninteractive
ENV SERVER_PATH /server
ENV TZ=Europe/Helsinki

RUN :\
    && apt-get update \
    && apt-get install -y \
        build-essential \
        python3-dev \
        libpcre3 \
        libpcre3-dev \
        jq\
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN pip3 install uwsgi -I --no-cache-dir

WORKDIR ${SERVER_PATH}
COPY requirements.txt ./
RUN pip3 install -r requirements.txt

COPY . ./
RUN chown -R www-data:www-data .

CMD ["uwsgi","app.ini"]
