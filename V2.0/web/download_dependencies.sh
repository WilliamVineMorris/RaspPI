#!/bin/bash
# Quick Download Script for Pi Offline Dependencies
# Use this if the Python script fails or requests library is missing
# Make executable with: chmod +x download_dependencies.sh

echo "🌐 Downloading offline dependencies for Pi hotspot operation..."

# Navigate to static/js directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JS_DIR="$SCRIPT_DIR/static/js"

echo "📁 Creating directory: $JS_DIR"
mkdir -p "$JS_DIR"
cd "$JS_DIR"
echo "📁 Current directory: $(pwd)"

# Download Socket.IO
echo "📦 Downloading Socket.IO..."
if wget -O socket.io.min.js "https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js" 2>/dev/null; then
    echo "✅ Socket.IO downloaded successfully"
elif curl -o socket.io.min.js "https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js" 2>/dev/null; then
    echo "✅ Socket.IO downloaded successfully (via curl)"
else
    echo "❌ Failed to download Socket.IO - check internet connection"
fi

# Download Plotly.js
echo "📦 Downloading Plotly.js..."
if wget -O plotly-2.27.1.min.js "https://cdn.plot.ly/plotly-2.27.1.min.js" 2>/dev/null; then
    echo "✅ Plotly.js downloaded successfully"
elif curl -o plotly-2.27.1.min.js "https://cdn.plot.ly/plotly-2.27.1.min.js" 2>/dev/null; then
    echo "✅ Plotly.js downloaded successfully (via curl)"
else
    echo "❌ Failed to download Plotly.js - check internet connection"
fi

# Check file sizes
echo ""
echo "📊 Download Summary:"
if [ -f "socket.io.min.js" ]; then
    size=$(stat -c%s "socket.io.min.js" 2>/dev/null || stat -f%z "socket.io.min.js" 2>/dev/null || echo "unknown")
    echo "✅ socket.io.min.js: $size bytes"
else
    echo "❌ socket.io.min.js: Missing"
fi

if [ -f "plotly-2.27.1.min.js" ]; then
    size=$(stat -c%s "plotly-2.27.1.min.js" 2>/dev/null || stat -f%z "plotly-2.27.1.min.js" 2>/dev/null || echo "unknown")
    echo "✅ plotly-2.27.1.min.js: $size bytes"
else
    echo "❌ plotly-2.27.1.min.js: Missing"
fi

echo ""
echo "🎉 Download complete! Restart the web server to use offline dependencies."
echo "📡 Pi hotspot should now work without internet connection."