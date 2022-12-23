FROM python:3.9-slim-bullseye

RUN apt-get update && apt-get install -y \
    git \
    # Required for installing/upgrading postgres:
    postgresql postgresql-client libpq-dev \
    # installs gcc
    build-essential \
    # memcahcd
    libmemcached-dev zlib1g-dev libjpeg-dev

# Set work directory
RUN mkdir /app
WORKDIR /app

# Copy requirements.txt
COPY ./requirements.txt /app/requirements.txt

# Install dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy project code
COPY . /app

# Prepare for release
# RUN chmod +x release.sh
RUN python manage.py collectstatic --no-input

HEALTHCHECK --interval=10s --timeout=3s \
  CMD curl -f -s http://0.0.0.0:8000/health/ || echo "Failed Docker Healthcheck" && exit 1

EXPOSE 8000

CMD ddtrace-run gunicorn --bind 0.0.0.0:8000 quixotic_backend.wsgi
