.PHONY: install lint format typecheck test check parse-sample compose-check notebook-check clean pre-commit

install:
	uv sync

lint:
	uv run ruff check .

format:
	uv run ruff format .

typecheck:
	uv run mypy scripts tests

test:
	uv run pytest -v

compose-check:
	docker compose config >/tmp/open5gs_lab_compose_config.txt

notebook-check:
	python3 -m json.tool notebooks/session_establishment_analysis.ipynb >/dev/null
	uv run nbqa ruff notebooks

parse-sample:
	uv run python scripts/parse_attach_logs.py logs/*sample.txt -o /tmp/parsed_attach_events.csv
	uv run python scripts/parse_attach_logs.py logs/*sample.txt -o /tmp/parsed_attach_events.json --json

pre-commit:
	uv run pre-commit run --all-files

check: compose-check lint typecheck test parse-sample notebook-check
	for f in scripts/*.sh; do bash -n "$$f"; done
	uv run ruff format --check .

clean:
	rm -f logs/parsed_attach_events.csv logs/parsed_attach_events.json
	rm -rf .mypy_cache .pytest_cache .ruff_cache
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
