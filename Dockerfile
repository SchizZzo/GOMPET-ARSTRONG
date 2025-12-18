FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /code

RUN apt-get update && apt-get install -y graphviz \
    && rm -rf /var/lib/apt/lists/*

# Instalacja GDAL i innych niezbędnych bibliotek systemowych
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gdal-bin \
    libgdal-dev \
    python3-gdal \
    && rm -rf /var/lib/apt/lists/*

RUN apt update && apt install -y gdal-bin libgdal-dev python3-gdal

# Ustawienie zmiennych środowiskowych (dla Pythona)
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal
# Sprawdź wersję GDAL i zainstaluj zgodny pakiet Pythona
#RUN pip install --upgrade pip setuptools wheel && \
#    pip install GDAL==$(gdal-config --version)

# 4. Ustawienia dla Proj
WORKDIR /code
COPY requirements.txt ./
RUN pip install --upgrade pip & pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000

RUN python django/gompet_new/manage.py collectstatic --noinput


CMD ["gunicorn", "gompet_new.asgi:application", "--workers", "4", "--bind", "0.0.0:8000", "--log-level", "info"]