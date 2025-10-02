#!/usr/bin/env python3
"""
Download Plotly.js library for local hosting
This script tries multiple CDN sources to download Plotly.js
"""

import os
import sys

def download_plotly():
    """Download Plotly.js to the static/js directory using requests library"""
    
    # Check if requests is available
    try:
        import requests
    except ImportError:
        print("❌ Error: 'requests' library not found")
        print("   Install with: pip install requests")
        return False
    
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
        if file_size > 1000000:  # > 1MB
            print(f"✅ Plotly.js already exists ({file_size:,} bytes)")
            print("   Skipping download. Delete the file to re-download.")
            return True
    
    # Try multiple CDN sources
    cdn_sources = [
        {
            'name': 'cdn.plot.ly',
            'url': 'https://cdn.plot.ly/plotly-2.27.1.min.js'
        },
        {
            'name': 'jsDelivr',
            'url': 'https://cdn.jsdelivr.net/npm/plotly.js@2.27.1/dist/plotly.min.js'
        },
        {
            'name': 'unpkg',
            'url': 'https://unpkg.com/plotly.js@2.27.1/dist/plotly.min.js'
        },
        {
            'name': 'cdnjs (Cloudflare)',
            'url': 'https://cdnjs.cloudflare.com/ajax/libs/plotly.js/2.27.1/plotly.min.js'
        }
    ]
    
    for cdn in cdn_sources:
        print(f"\n🔄 Trying {cdn['name']}...")
        print(f"   URL: {cdn['url']}")
        
        try:
            # Download with timeout
            response = requests.get(cdn['url'], timeout=30, stream=True)
            response.raise_for_status()
            
            # Get file size
            total_size = int(response.headers.get('content-length', 0))
            
            # Download with progress
            downloaded = 0
            chunk_size = 8192
            
            with open(plotly_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = int(downloaded * 100 / total_size)
                            sys.stdout.write(f"\r   Progress: {percent}% ({downloaded:,} / {total_size:,} bytes)")
                            sys.stdout.flush()
            
            print()  # New line after progress
            
            # Verify download
            file_size = os.path.getsize(plotly_path)
            print(f"✅ Download complete from {cdn['name']}! ({file_size:,} bytes)")
            
            # Verify it's JavaScript
            with open(plotly_path, 'r', encoding='utf-8') as f:
                first_line = f.readline()
                if 'plotly' in first_line.lower() or 'function' in first_line.lower() or '/*' in first_line:
                    print("✅ File verified - appears to be valid JavaScript")
                    return True
                else:
                    print("⚠️  Warning: File may not be valid Plotly.js")
                    print(f"   First line: {first_line[:100]}")
                    # Try next CDN
                    continue
                    
        except requests.exceptions.Timeout:
            print(f"❌ Timeout - {cdn['name']} took too long")
            continue
            
        except requests.exceptions.ConnectionError:
            print(f"❌ Connection error - Cannot reach {cdn['name']}")
            continue
            
        except requests.exceptions.HTTPError as e:
            print(f"❌ HTTP error - {e}")
            continue
            
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            continue
    
    # If we get here, all CDNs failed
    print("\n" + "="*60)
    print("❌ All CDN sources failed!")
    print("="*60)
    print("\nPossible causes:")
    print("  - No internet connection")
    print("  - Firewall blocking CDN access")
    print("  - DNS issues")
    print("\nAlternative solutions:")
    print("  1. Download on PC and transfer via Git/USB/SCP")
    print("  2. Use a different network")
    print("  3. Check firewall settings")
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
