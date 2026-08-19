.PHONY: install run clean

install:
	python3 -m venv venv
	./venv/bin/pip install -q -r requirements.txt
	@if [ ! -f .env ]; then \
		printf '# Get a free key at console.groq.com\nGROQ_API_KEY=gsk_...\n\n# Optional\nCOORDINATOR_MODEL=openai/gpt-oss-120b\nPHONE_MODEL=openai/gpt-oss-20b\n' > .env; \
		echo "-> .env created. Add your GROQ_API_KEY before running."; \
	fi
	@echo "-> Setup complete. Run: make run"

run:
	./venv/bin/python demo.py

clean:
	rm -rf venv __pycache__ src/__pycache__ .env
