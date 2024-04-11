FROM python:3.11
WORKDIR /app
COPY rtl_watcher.py /app
COPY lib /app/lib
COPY requirements.txt /app
RUN pip install -r requirements.txt
RUN apt update && apt install -y ffmpeg

ENTRYPOINT []
