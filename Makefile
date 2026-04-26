# Simple helpers for management commands

DC=docker-compose
MANAGE=$(DC) run --rm web python manage.py
DB_SERVICE=db
DB_USER=postgres
DB_NAME=gis
BACKUP_DIR=BACKUP/db
BACKUP_TIMESTAMP:=$(shell powershell -NoProfile -Command "(Get-Date -Format yyyyMMdd_HHmmss)")
BACKUP_FILE:=$(BACKUP_DIR)/django_$(BACKUP_TIMESTAMP).sql






.PHONY: help makemigrations migrate swagger swagger-json swagger-v3 swagger-v3-json create-extension backup-db restore-db


help:
	@echo "Available commands:"
	
	@echo "  make makemigrations - run makemigrations"
	@echo "  make migrate     - run migrations"
	@echo "  make runserver   - start the server"
	@echo "  make build       - build docker images"
	@echo "  make down        - stop the server"
	@echo "  make collectstatic - collect static files"
	@echo "  make createsuperuser - create a superuser"
	@echo "  make swagger     - generate OpenAPI YAML schema"
	@echo "  make swagger-json - generate OpenAPI JSON schema"
	@echo "  make swagger-v3  - generate readable v3 OpenAPI YAML schema"
	@echo "  make swagger-v3-json - generate readable v3 OpenAPI JSON schema"
	@echo "  make backup-db   - create PostgreSQL backup to BACKUP/db/"
	@echo "  make restore-db RESTORE_FILE=... - restore PostgreSQL backup from file"





makemigrations:
	$(MANAGE) makemigrations

migrate:
	$(MANAGE) migrate

collectstatic:
	$(MANAGE) collectstatic

runserver:
	$(DC) up -d

run:
	$(DC) up

run-backend:
	$(DC) up web nginx db redis mailpit



down:
	$(DC) down	

build:
	$(DC) build

createsuperuser:
	$(MANAGE) createsuperuser

populatedb:
	$(MANAGE) populatedb


graphmodels:
	$(MANAGE) graph_models -a -o project_models.svg


	


all:
	$(MAKE) makemigrations
	$(MAKE) migrate
	$(MAKE) collectstatic
	$(MAKE) populatedb
	$(MAKE) createsuperuser
	$(MAKE) run
	

nginx:
	$(DC) exec nginx nginx -s reload

build-no-cache:
	$(DC) build --no-cache

test:
	$(MANAGE) test animals

test-common:
	$(MANAGE) test common

test-users:
	$(MANAGE) test users

test-posts:
	$(MANAGE) test posts

swagger:
	$(DC) run --rm web sh -c "mkdir -p docs && python manage.py spectacular --file docs/openapi.yaml"

swagger-json:
	$(DC) run --rm web sh -c "mkdir -p docs && python manage.py spectacular --format openapi-json --file docs/openapi.json"

swagger-v3:
	$(DC) run --rm web sh -c "mkdir -p docs && python manage.py spectacular --file docs/openapi-v3.yaml"

swagger-v3-json:
	$(DC) run --rm web sh -c "mkdir -p docs && python manage.py spectacular --format openapi-json --file docs/openapi-v3.json"


create-extension:
	$(DC) exec db sh -c 'psql -U "$${POSTGRES_USER:-postgres}" -d "$${POSTGRES_DB:-gis}" -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"'


backup-db:
	$(DC) run --rm web sh -c "mkdir -p $(BACKUP_DIR)"
	$(DC) exec db pg_dump -U $(DB_USER) -d $(DB_NAME) > $(BACKUP_FILE)
	@echo "Database backup created at $(BACKUP_FILE)"

restore-db:
ifndef RESTORE_FILE
	$(error RESTORE_FILE is not set. Usage: make restore-db RESTORE_FILE=path/to/backup.sql)
endif
	$(DC) exec -i db psql -U $(DB_USER) -d $(DB_NAME) < $(RESTORE_FILE)
	@echo "Database restored from $(RESTORE_FILE)"

