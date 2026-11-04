#!/bin/sh
# Create a self-contained venv in this folder and install dependencies.
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install -q -r requirements.txt
echo "setup done: .venv ready"
