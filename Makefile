.PHONY: up down logs test clean

# Start the application
up:
	docker compose up -d --build

# Stop and remove containers and volumes
down:
	docker compose down -v

# Follow API logs
logs:
	docker compose logs -f api

# Run tests inside container
test:
	docker compose exec api pytest /app/tests -v

# Run tests locally (requires dependencies installed)
test-local:
	pytest tests/ -v

# Clean up Docker resources
clean:
	docker compose down -v --rmi local
	docker system prune -f

# Rebuild without cache
rebuild:
	docker compose build --no-cache
	docker compose up -d

# Show running containers
status:
	docker compose ps

# Shell into the container
shell:
	docker compose exec api /bin/bash