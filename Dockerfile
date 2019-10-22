FROM apluslms/service-base:python3-1.5
#FROM tiangolo/uwsgi-nginx-flask:python3.7

COPY . /srv/static_management
WORKDIR /srv/static_management/

RUN :\
    && adduser --system --disabled-password --gecos "static management system,,," --ingroup nogroup static_management \
    && chown static_management.nogroup /srv/static_management \
    && pip3 install -r requirements.txt \
    && rm requirements.txt

EXPOSE 5000
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]