# infra/docker/Dockerfile  (Alpine, no apt)
FROM python:3.12-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System deps for mysqlclient & Pillow (pin apk mirrors explicitly)
RUN printf '%s\n' \
      'https://dl-cdn.alpinelinux.org/alpine/latest-stable/main' \
      'https://dl-cdn.alpinelinux.org/alpine/latest-stable/community' \
      > /etc/apk/repositories \
 && apk update \
 && apk add --no-cache \
      build-base mariadb-connector-c-dev \
      jpeg-dev zlib-dev libpng-dev curl

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . /app

COPY infra/docker/entrypoint.sh /entrypoint.sh
# Normalize CRLF if present; make executable
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
