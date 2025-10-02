#!/bin/bash

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Activate the virtual environment
source "$SCRIPT_DIR/venv/bin/activate"

# Run the Python script
python "$SCRIPT_DIR/update_stocks.py"

# Deactivate the virtual environment
deactivate

