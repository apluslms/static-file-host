#!/bin/bash
image_static=client-static
image_yaml=client-yaml
docker build --rm --build-arg UPLOAD_FILE=html -t ${image_static} .
docker build --rm --build-arg UPLOAD_FILE=yaml -t ${image_yaml} .