FROM ubuntu:bionic
MAINTAINER Gregory B. Rehm
ENV TZ=America/Los_Angeles

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
RUN apt-get -y update && apt-get install -y python-scipy python-dev python-pip python-pandas
RUN apt-get install -y nginx supervisor inotify-tools
RUN useradd ubuntu -m -d /home/ubuntu

RUN mkdir /home/ubuntu/apl
COPY source/ /home/ubuntu/apl
COPY apl-supervisor.conf /etc/supervisor/conf.d/apl.conf
COPY nginx.conf /etc/nginx/nginx.conf
COPY apl-nginx /etc/nginx/sites-available/
COPY supervisord.conf /etc/supervisor/
COPY prod_config.py /home/ubuntu/apl/config.py
RUN rm /etc/nginx/sites-enabled/default
RUN ln -s /etc/nginx/sites-available/apl-nginx /etc/nginx/sites-enabled/
RUN chown -R ubuntu:ubuntu /home/ubuntu/apl
RUN mkdir /var/log/apl
RUN chown -R ubuntu:ubuntu /var/log/apl
RUN pip install -U pip
RUN pip install -r /home/ubuntu/apl/requirements.txt

EXPOSE 80
CMD service nginx restart && supervisord -c /etc/supervisor/supervisord.conf
