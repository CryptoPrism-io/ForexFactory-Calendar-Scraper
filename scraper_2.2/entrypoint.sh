#!/bin/bash
# Entrypoint script to start Xvfb before running the Python script

# Start Xvfb on display :99
echo "Starting Xvfb virtual display on :99..."
Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset &
XVFB_PID=$!

# Wait a moment for Xvfb to start
sleep 2

# Verify Xvfb is running
if ! ps -p $XVFB_PID > /dev/null; then
    echo "ERROR: Failed to start Xvfb"
    exit 1
fi

echo "Xvfb started successfully (PID: $XVFB_PID)"
echo "Display: $DISPLAY"

# Execute the command passed to the container
exec "$@"
