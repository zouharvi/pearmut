.PHONY: install dev build run lint test clean

install:
	python3 -m pip install -r requirements.txt
	cd web && npm install

dev:
	pip install -e ".[dev]"
	cd web && npm install

build:
	rm -rf server/static/
	cd web && npm run build

run: dev build
	pearmut run --port 8001

lint: dev
	ruff check server
	ruff check --select=I server

test: dev
	pytest server/tests/*

clean:
	rm -rf server/static/ build/ dist/ pearmut.egg-info/
