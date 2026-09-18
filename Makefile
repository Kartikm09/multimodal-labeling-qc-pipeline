PYTHON ?= python3
.PHONY: verify media demo browser
verify:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v
	PYTHONPATH=src $(PYTHON) -m compileall -q src scripts tests
media:
	PYTHONPATH=src $(PYTHON) scripts/generate_temporal_fixtures.py
demo:
	PYTHONPATH=src $(PYTHON) -m qc_pipeline.review_server
browser:
	npx playwright test
