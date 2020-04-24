FROM ubuntu:bionic

RUN apt-get update && apt-get install -y \
    python3 python3-pip

MKDIR /vpmo_gremlin
WORKDIR /vpmo_gremlin
COPY requirements.txt /vpmo_gremlin/
RUN pip3 install -r requirements.txt
COPY . /vpmo_gremlin/

ENV LC_ALL C.UTF-8
ENV LANG C.UTF-8
ENV PYTHONUNBUFFERED 1
ENV FLASK_APP api.py

# Runs the flask app at :5000
RUN python3 -m flask run --host=0.0.0.0
