.PHONY: up down test load-test simulate logs clean

up:
	docker-compose -f deploy/docker-compose.yml up -d

down:
	docker-compose -f deploy/docker-compose.yml down

build:
	docker-compose -f deploy/docker-compose.yml build

logs:
	docker-compose -f deploy/docker-compose.yml logs -f

test:
	cd backend && python -m pytest ../tests/ -v

load-test:
	cd backend && python -m pytest ../tests/load/ -v --timeout=300

simulate:
	docker-compose -f deploy/docker-compose.yml --profile testing up simulator

clean:
	docker-compose -f deploy/docker-compose.yml down -v
