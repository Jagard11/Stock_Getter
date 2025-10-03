#!/bin/bash
# Start the Inspector web server

cd "$(dirname "$0")"

# Pull latest updates from git
echo "Checking for updates..."
git pull

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Install dependencies if needed
if ! python -c "import fastapi" 2>/dev/null; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

# Run the server
echo "Starting Inspector web server..."
echo "Visit http://localhost:8000 in your browser"
python server.py

