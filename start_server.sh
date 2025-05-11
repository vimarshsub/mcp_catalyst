#!/bin/bash

# Source the virtual environment
source venv/bin/activate

echo "Starting Gunicorn server..."

# Start Gunicorn with eventlet worker in the background
nohup gunicorn --workers 2 --worker-class eventlet --bind 0.0.0.0:5001 app:app --timeout 120 --log-file server.log --log-level debug > gunicorn.log 2>&1 &

# Wait a moment for the server to start
sleep 2

# Check if the server is running
if pgrep -f "gunicorn.*app:app" > /dev/null; then
    echo "Gunicorn server started successfully."
    echo "Server logs are in server.log"
    echo "Gunicorn logs are in gunicorn.log"
else
    echo "Error: Gunicorn server failed to start. Check gunicorn.log for details."
fi

