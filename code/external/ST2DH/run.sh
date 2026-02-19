#!/usr/bin/env bash

# enable debugging
export FLASK_DEBUG=true
export FLASK_APP=app.py

echo "Starting Flask app... $FLASK_APP"
uv run -- flask run --host=0.0.0.0  -p 5004

