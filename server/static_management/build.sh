#!/bin/bash
server_static=server-static
server_yaml=server-yaml
docker build --rm --build-arg SERVER_FILE=html -t ${server_static} .
docker build --rm --build-arg SERVER_FILE=yaml -t ${server_yaml} .

docker tag ${server_static} qianqianq/${server_static}:latest
docker push qianqianq/${server_static}:latest

docker tag ${server_yaml} qianqianq/${server_yaml}:latest
docker push qianqianq/${server_yaml}:latest