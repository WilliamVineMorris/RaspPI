#!/usr/bin/env python3
"""
Download Offline Dependencies for Pi Hotspot Operation

This script downloads CDN dependencies to local files so the web interface
works without internet connection when connected directly to Pi hotspot.
"""

import requests
import os
from pathlib import Path

def download_file(url, local_path):
    """Download a file from URL to local path"""
    try:
        print(f"Downloading {url}...")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        with open(local_path, 'wb') as f:
            f.write(response.content)
        
        print(f"✅ Downloaded to {local_path}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to download {url}: {e}")
        return False

def main():
    """Download all required offline dependencies"""
    
    # Get the static directory path
    script_dir = Path(__file__).parent
    static_dir = script_dir / 'static'
    js_dir = static_dir / 'js'
    
    print("🌐 Downloading offline dependencies for Pi hotspot operation...")
    print(f"Target directory: {js_dir}")
    
    # Dependencies to download
    dependencies = [
        {
            'url': 'https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js',
            'path': js_dir / 'socket.io.min.js',
            'description': 'Socket.IO for real-time communication'
        },
        {
            'url': 'https://cdn.plot.ly/plotly-2.27.1.min.js',
            'path': js_dir / 'plotly-2.27.1.min.js', 
            'description': 'Plotly.js latest version'
        }
    ]
    
    success_count = 0
    total_count = len(dependencies)
    
    for dep in dependencies:
        print(f"\n📦 {dep['description']}")
        if download_file(dep['url'], dep['path']):
            success_count += 1
    
    print(f"\n📊 Download Summary:")
    print(f"✅ Successful: {success_count}/{total_count}")
    print(f"❌ Failed: {total_count - success_count}/{total_count}")
    
    if success_count == total_count:
        print("\n🎉 All dependencies downloaded successfully!")
        print("📡 Pi hotspot will now work without internet connection")
    else:
        print("\n⚠️ Some downloads failed - check internet connection and try again")
    
    return success_count == total_count

if __name__ == '__main__':
    main()