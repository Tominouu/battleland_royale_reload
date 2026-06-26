#!/bin/bash
# Start the Battlelands private server
DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR"

source venv/bin/activate
export FLASK_ENV=development
python app.py
