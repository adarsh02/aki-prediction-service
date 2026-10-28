FROM ubuntu:noble
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get -yq install python3-pip python3-venv
WORKDIR /app
RUN python3 -m venv /app/venv
COPY requirements.txt /app/requirements.txt
RUN /app/venv/bin/pip install --no-cache-dir -r /app/requirements.txt
COPY app /app
EXPOSE 8000
ENTRYPOINT ["/app/venv/bin/python3", "-u", "/app/main.py"]
