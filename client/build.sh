#!/bin/bash
image=file-management-client

docker build --rm -t ${image} .

#docker tag ${image} qianqianq/${image}:latest
#docker push qianqianq/${image}:latest
