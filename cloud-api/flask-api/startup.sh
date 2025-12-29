#!/bin/bash
# Startup script for Azure App Service
# Starts Flask API with gunicorn using eventlet workers for WebSocket support

# Set PORT if not already set (Azure sets this automatically)
PORT="${PORT:-8000}"

# Start gunicorn with eventlet worker for Flask-SocketIO
exec gunicorn \
    --worker-class eventlet \
    -w 1 \
    --bind "0.0.0.0:$PORT" \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    app:app
