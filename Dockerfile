#####
## Docker image for the JASMIN Cloud API
#####


FROM python:3.9.5

# Create the user that will be used to run the app
ENV APP_UID 1001
ENV APP_GID 1001
ENV APP_USER app
ENV APP_GROUP app
RUN groupadd --gid $APP_GID $APP_GROUP && \
    useradd \
      --no-create-home \
      --no-user-group \
      --gid $APP_GID \
      --shell /sbin/nologin \
      --uid $APP_UID \
      $APP_USER

RUN apt-get update && \
    apt-get install -y tini && \
    rm -rf /var/lib/apt/lists/*

# Don't buffer stdout and stderr as it breaks realtime logging
ENV PYTHONUNBUFFERED 1

# Install gunicorn as the WSGI server, whitenoise to handle static files and
# django-flexi-settings for smart handling of settings
RUN pip install --no-cache-dir \
      'gunicorn==20.0.4' \
      'whitenoise==5.2.0' \
      'git+https://github.com/stackhpc/django-flexi-settings.git@9540ccdaff70b075658bfe5550e5b3626d5e95cd#egg=django_flexi_settings'

# Install Gunicorn config
COPY ./etc/gunicorn /etc/gunicorn

# Install dependencies
# Doing this separately by copying only the requirements file enables better use of the build cache
COPY ./requirements.txt /application/
RUN pip install --no-deps --requirement /application/requirements.txt

# Install the application itself
COPY . /application
RUN pip install --no-deps -e /application

# Install application configuration using flexi-settings
ENV DJANGO_SETTINGS_MODULE flexi_settings.settings
ENV DJANGO_FLEXI_SETTINGS_ROOT /etc/django/settings.py
COPY ./etc/django /etc/django
RUN mkdir -p /etc/django/settings.d

# Collect the static files
RUN django-admin collectstatic

# By default, serve the app on port 8080 using the app user
EXPOSE 8080
USER $APP_UID
ENTRYPOINT ["tini", "-g", "--"]
CMD ["gunicorn", "--config", "/etc/gunicorn/conf.py", "jasmin_cloud_site.wsgi:application"]