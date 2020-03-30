#!/bin/bash
image_static=client-static
image_yaml=client-yaml
docker build --rm --build-arg UPLOAD_FILE=html -t ${image_static} .
docker build --rm --build-arg UPLOAD_FILE=yaml -t ${image_yaml} .

docker tag ${image_static} qianqianq/${image_static}:latest
docker push qianqianq/${image_static}:latest

docker tag ${image_yaml} qianqianq/${serve_yaml}:latest
docker push qianqianq/${server_yaml}:latest