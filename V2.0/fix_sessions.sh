#!/bin/bash
echo "🔧 Fixing corrupted sessions.html file..."
cd "$(dirname "$0")"
python3 fix_sessions_html.py