# Simple helpers for management commands

DC=docker-compose
MANAGE=$(DC) run --rm web python manage.py


.PHONY: help makemigrations migrate


help:
	@echo "Available commands:"
	
	@echo "  make makemigrations - run makemigrations"
	@echo "  make migrate     - run migrations"
	@echo "  make runserver   - start the server"
	@echo "  make build       - build docker images"
	@echo "  make down        - stop the server"
	@echo "  make collectstatic - collect static files"
	@echo "  make createsuperuser - create a superuser"





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

down:
	$(DC) down	

build:
	$(DC) build

createsuperuser:
	$(MANAGE) createsuperuser

populatedb:
	$(MANAGE) populatedb


all:
	$(MAKE) makemigrations
	$(MAKE) migrate
	$(MAKE) collectstatic
	$(MAKE) populatedb
	$(MAKE) createsuperuser
	$(MAKE) run
	