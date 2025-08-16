#!/bin/bash

# Production startup script
echo "Starting KML to SQL Converter..."

# Create directories if they don't exist
mkdir -p uploads results

# Start the application with Gunicorn (increased timeout and fewer workers for better stability)
exec gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 600 --max-requests 1000 --preload app:app
