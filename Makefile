.PHONY: install lint format typecheck test check parse-sample compose-check notebook-check clean pre-commit validate-config preflight lab-up lab-status subscriber-add baseline-test lab-down collect-evidence scenario scenario-list scenario-validate capture-start capture-stop coverage

install:
	uv sync

lint:
	uv run ruff check .

format:
	uv run ruff format .

typecheck:
	uv run mypy src scripts tests

test:
	uv run pytest -m "not runtime" -v

coverage:
	uv run pytest -m "not runtime" --cov=src/fiveg_lab --cov=scripts --cov-report=term-missing

compose-check:
	docker compose config >/tmp/open5gs_lab_compose_config.txt

validate-config:
	uv run 5g-lab validate-config

preflight:
	./scripts/preflight.sh

lab-up: validate-config
	./scripts/start_lab.sh

lab-status:
	docker compose --profile ran --profile tools ps

subscriber-add: validate-config
	./scripts/add_subscriber.sh

baseline-test:
	SCENARIO=baseline_e2e ./scripts/run_scenario.sh

scenario:
	./scripts/run_scenario.sh $(SCENARIO)

scenario-list:
	uv run 5g-lab scenario list

scenario-validate:
	uv run 5g-lab scenario validate

collect-evidence:
	./scripts/collect_logs.sh

capture-start:
	./scripts/capture_start.sh

capture-stop:
	./scripts/capture_stop.sh

lab-down:
	./scripts/stop_lab.sh

notebook-check:
	python3 -m json.tool notebooks/session_establishment_analysis.ipynb >/dev/null
	uv run nbqa ruff notebooks

parse-sample:
	uv run python scripts/parse_attach_logs.py logs/*sample.txt -o /tmp/parsed_attach_events.csv
	uv run python scripts/parse_attach_logs.py logs/*sample.txt -o /tmp/parsed_attach_events.json --json

pre-commit:
	uv run pre-commit run --all-files

check: compose-check validate-config scenario-validate lint typecheck test parse-sample notebook-check
	for f in scripts/*.sh; do bash -n "$$f"; done
	uv run ruff format --check .

clean:
	rm -f logs/parsed_attach_events.csv logs/parsed_attach_events.json
	rm -f .coverage
	rm -rf .mypy_cache .pytest_cache .ruff_cache
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
