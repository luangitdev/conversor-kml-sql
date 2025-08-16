#!/bin/bash

# Production startup script
echo "Starting KML to SQL Converter..."

# Create directories if they don't exist
mkdir -p uploads results

# Start the application with Gunicorn
exec gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 300 --max-requests 1000 app:app
