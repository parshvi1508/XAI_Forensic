.PHONY: audit analyse charts verify clean

PYTHON ?= .venv/Scripts/python

audit:
	$(PYTHON) -m audit.runner
	$(PYTHON) -m audit.analyse_results
	$(PYTHON) -m audit.generate_charts

analyse:
	$(PYTHON) -m audit.analyse_results

charts:
	$(PYTHON) -m audit.generate_charts

verify:
	$(PYTHON) -c "from audit.verify import verify_reproducibility; verify_reproducibility()"

clean:
	$(PYTHON) -c "import glob, os; [os.remove(f) for f in glob.glob('audit/results/*.csv') + glob.glob('audit/results/*.json') + glob.glob('audit/results/*.png')]"
