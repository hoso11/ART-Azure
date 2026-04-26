.PHONY: up down build migrate seed test logs clean restart

# Start all services
up:
	docker-compose up -d

# Start with build
up-build:
	docker-compose up -d --build

# Stop all services
down:
	docker-compose down

# Rebuild all containers
build:
	docker-compose build

# Run database migrations
migrate:
	docker-compose run --rm migrate

# Seed database with sample data
seed:
	docker-compose exec backend python -m scripts.seed

# Run backend tests
test:
	docker-compose exec backend pytest tests/ -v

# View logs
logs:
	docker-compose logs -f

# View specific service logs
logs-backend:
	docker-compose logs -f backend

logs-frontend:
	docker-compose logs -f frontend

logs-worker:
	docker-compose logs -f worker

# Clean everything including volumes
clean:
	docker-compose down -v --remove-orphans

# Restart a specific service
restart-%:
	docker-compose restart $*

# Create a new alembic migration
migration:
	docker-compose exec backend alembic revision --autogenerate -m "$(msg)"

# Shell into backend container
shell:
	docker-compose exec backend bash

# Shell into frontend container
shell-frontend:
	docker-compose exec frontend sh
