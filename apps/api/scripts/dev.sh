#!/bin/bash
# Development startup script for API

set -e

echo "Starting Smart Stock Bot API (development mode)..."

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

# Start the development server
echo "Starting uvicorn..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
