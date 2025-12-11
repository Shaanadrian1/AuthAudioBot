#!/bin/bash
# Startup script for Render.com

# Create necessary directories
mkdir -p data logs uploads

# Install FFmpeg if not present
if ! command -v ffmpeg &> /dev/null; then
    echo "FFmpeg not found, installing..."
    apt-get update && apt-get install -y ffmpeg
fi

# Run the application
python -m app.main