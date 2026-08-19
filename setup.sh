#!/bin/bash
# For machines without make. Run: bash setup.sh

set -e

echo "Setting up DME Coordinator..."

python3 -m venv venv
source venv/bin/activate
pip install -q -r requirements.txt

if [ ! -f .env ]; then
    printf '# Get a free key at console.groq.com\nGROQ_API_KEY=gsk_...\n\n# Optional\nCOORDINATOR_MODEL=openai/gpt-oss-120b\nPHONE_MODEL=openai/gpt-oss-20b\n' > .env
    echo ""
    echo "-> .env created. Open it and add your GROQ_API_KEY."
else
    echo "-> .env already exists."
fi

echo ""
echo "Setup complete. Run:"
echo "  source venv/bin/activate && python demo.py"
echo "  or: make run"
