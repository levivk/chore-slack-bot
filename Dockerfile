#syntax=docker/dockerfile:1

FROM python:3.13-slim-bullseye

ENV TZ="America/Chicago"
ENV PIP_ROOT_USER_ACTION=ignore

WORKDIR /app
RUN pip3 install --upgrade pip
# RUN apt-get-update && apt-get-install ffmpeg libsm6 libxext6 -y
COPY requirements.txt .
RUN pip3 install -r requirements.txt
COPY src src
# COPY data data

CMD [ "python3", "src/main.py"]
