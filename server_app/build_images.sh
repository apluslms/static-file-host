#!/bin/bash
server_static=server-static
server_yaml=server-yaml
user_name=qianqianq
docker build --rm --build-arg SERVER_FILE=html -t ${server_static} .
docker build --rm --build-arg SERVER_FILE=yaml -t ${server_yaml} .

docker tag ${server_static} ${user_name}/${server_static}:latest
docker push qianqianq/${server_static}:latest

docker tag ${server_yaml} ${user_name}/${server_yaml}:latest
docker push qianqianq/${server_yaml}:latest