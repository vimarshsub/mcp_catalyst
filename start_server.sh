#!/bin/bash

# Activate virtual environment
source /home/ubuntu/mcp_server_project/venv/bin/activate

# Start the Gunicorn server
# Make sure CATALYST_BASE_URL, CATALYST_USERNAME, CATALYST_PASSWORD are set in the environment

echo "Starting Gunicorn server..."
echo "CATALYST_BASE_URL set to: ${CATALYST_BASE_URL}"
echo "Make sure CATALYST_USERNAME and CATALYST_PASSWORD are also set in your environment or defaults are correct."

# Using --worker-class gevent for better SSE support if available, otherwise default sync workers
# Using --timeout 120 to prevent worker timeouts during long SSE connections or slow API responses
# Logging to server.log
gunicorn --workers 2 --worker-class eventlet --bind 0.0.0.0:5001 app:app --timeout 120 --log-file /home/ubuntu/mcp_server_project/server.log --log-level debug

if [ $? -eq 0 ]; then
    echo "Gunicorn server started successfully."
else
    echo "Error: Gunicorn server failed to start. Check server.log for details."
    exit 1
fi

