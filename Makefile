.PHONY: up down build logs restart ps clean

up:
	docker compose up -d

up-build:
	docker compose up -d --build

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

logs-backend:
	docker compose logs -f backend

logs-mt5:
	docker compose logs -f mt5

restart:
	docker compose restart

restart-backend:
	docker compose restart backend

ps:
	docker compose ps

clean:
	docker compose down -v --remove-orphans

shell-backend:
	docker compose exec backend bash

shell-db:
	docker compose exec timescaledb psql -U trader -d trading

dev-frontend:
	cd frontend && npm run dev
