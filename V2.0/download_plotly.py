#!/usr/bin/env python3
"""
Download Plotly.js library for local hosting
This script downloads the Plotly.js library from CDN and saves it locally
so the 3D visualizer works without internet access.
"""

import os
import sys
import urllib.request
import urllib.error

def download_plotly():
    """Download Plotly.js to the static/js directory"""
    
    # Get the script directory and construct paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    static_js_dir = os.path.join(script_dir, 'web', 'static', 'js')
    plotly_path = os.path.join(static_js_dir, 'plotly-2.27.0.min.js')
    
    # Create directory if it doesn't exist
    os.makedirs(static_js_dir, exist_ok=True)
    
    print("📦 Downloading Plotly.js...")
    print(f"   Destination: {plotly_path}")
    
    # Check if file already exists
    if os.path.exists(plotly_path):
        file_size = os.path.getsize(plotly_path)
        if file_size > 1000000:  # > 1MB (Plotly is ~3.5MB)
            print(f"✅ Plotly.js already exists ({file_size:,} bytes)")
            print("   Skipping download. Delete the file to re-download.")
            return True
        else:
            print(f"⚠️  Existing file seems too small ({file_size:,} bytes)")
            print("   Re-downloading...")
    
    # Download from CDN
    url = "https://cdn.plotly.ly/plotly-2.27.0.min.js"
    
    try:
        print(f"   Downloading from: {url}")
        
        # Download with progress
        def reporthook(count, block_size, total_size):
            percent = int(count * block_size * 100 / total_size)
            sys.stdout.write(f"\r   Progress: {percent}% ({count * block_size:,} / {total_size:,} bytes)")
            sys.stdout.flush()
        
        urllib.request.urlretrieve(url, plotly_path, reporthook)
        print()  # New line after progress
        
        # Verify download
        file_size = os.path.getsize(plotly_path)
        print(f"✅ Download complete! ({file_size:,} bytes)")
        
        # Verify it's a JavaScript file
        with open(plotly_path, 'r', encoding='utf-8') as f:
            first_line = f.readline()
            if 'plotly' in first_line.lower() or 'function' in first_line.lower():
                print("✅ File verified - appears to be valid JavaScript")
                return True
            else:
                print("⚠️  Warning: File may not be valid Plotly.js")
                print(f"   First line: {first_line[:100]}")
                return False
                
    except urllib.error.URLError as e:
        print(f"❌ Download failed: {e}")
        print("   Possible causes:")
        print("   - No internet connection")
        print("   - CDN is blocked")
        print("   - Firewall settings")
        print("\n   Try manually downloading:")
        print(f"   1. Visit: {url}")
        print(f"   2. Save to: {plotly_path}")
        return False
    
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_plotly_load():
    """Test if Plotly can be loaded"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    plotly_path = os.path.join(script_dir, 'web', 'static', 'js', 'plotly-2.27.0.min.js')
    
    if not os.path.exists(plotly_path):
        print("❌ Plotly.js not found!")
        return False
    
    file_size = os.path.getsize(plotly_path)
    print(f"\n📊 Plotly.js Status:")
    print(f"   Location: {plotly_path}")
    print(f"   Size: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")
    
    if file_size < 1000000:
        print(f"   ⚠️  File seems too small (expected ~3.5 MB)")
        return False
    else:
        print(f"   ✅ File size looks good")
        return True

def main():
    print("=" * 60)
    print("Plotly.js Local Installation Script")
    print("=" * 60)
    print()
    
    success = download_plotly()
    
    print()
    test_plotly_load()
    
    print()
    print("=" * 60)
    if success:
        print("✅ Setup Complete!")
        print()
        print("Next steps:")
        print("1. Restart the web server:")
        print("   python3 run_web_interface.py")
        print()
        print("2. Refresh the browser page")
        print()
        print("3. The 3D visualizer should now work!")
    else:
        print("❌ Setup Failed")
        print()
        print("Manual installation:")
        print("1. Download: https://cdn.plotly.ly/plotly-2.27.0.min.js")
        print("2. Save to: web/static/js/plotly-2.27.0.min.js")
        print("3. Restart web server")
    print("=" * 60)

if __name__ == '__main__':
    main()
