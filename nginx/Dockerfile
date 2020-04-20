# Use the Nginx image
FROM nginx

ENV TZ=Europe/Helsinki

# Remove the default nginx.conf
RUN rm /etc/nginx/conf.d/default.conf

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Replace with our own nginx.conf
COPY nginx.conf /etc/nginx/conf.d/
