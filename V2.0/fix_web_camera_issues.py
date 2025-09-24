#!/usr/bin/env python3
"""
Quick fix for web interface camera and loading issues
"""

import sys
import os
from pathlib import Path

def fix_camera_streaming():
    """Enable all cameras for streaming and fix web loading issues"""
    print("🔧 Fixing Camera Streaming Issues...")
    
    web_interface_file = Path(__file__).parent / "web" / "web_interface.py"
    
    if not web_interface_file.exists():
        print("❌ Web interface file not found")
        return False
    
    try:
        # Read the file
        with open(web_interface_file, 'r') as f:
            content = f.read()
        
        # Find and fix the camera stream restriction
        original_lines = content.split('\n')
        fixed_lines = []
        
        in_camera_stream_function = False
        found_camera_restriction = False
        
        for i, line in enumerate(original_lines):
            if "def _generate_camera_stream(self, camera_id):" in line:
                in_camera_stream_function = True
                print("   Found camera stream function")
            
            # Fix the camera restriction
            if in_camera_stream_function and "if camera_id not in [0, '0', 'camera_1']:" in line:
                found_camera_restriction = True
                # Change to allow all cameras
                fixed_lines.append("        # Allow all cameras")
                fixed_lines.append("        if camera_id not in [0, 1, '0', '1', 'camera_1', 'camera_2']:")
                print("   ✅ Fixed camera restriction to allow both cameras")
                continue
            
            # Update the disabled camera message
            elif in_camera_stream_function and 'text = f"Camera {camera_id} Disabled"' in line:
                fixed_lines.append('                text = f"Camera {camera_id} Not Available"')
                continue
            
            # End of function detection
            elif in_camera_stream_function and line.strip().startswith("def ") and "_generate_camera_stream" not in line:
                in_camera_stream_function = False
            
            fixed_lines.append(line)
        
        if found_camera_restriction:
            # Write back the fixed content
            with open(web_interface_file, 'w') as f:
                f.write('\n'.join(fixed_lines))
            print("✅ Camera streaming restriction removed")
            return True
        else:
            print("⚠️  Camera restriction not found - may already be fixed")
            return True
            
    except Exception as e:
        print(f"❌ Failed to fix camera streaming: {e}")
        return False

def fix_web_loading_issues():
    """Fix common web loading issues"""
    print("🌐 Checking Web Loading Issues...")
    
    # Check if templates exist
    template_dir = Path(__file__).parent / "web" / "templates"
    static_dir = Path(__file__).parent / "web" / "static"
    
    critical_files = [
        template_dir / "manual.html",
        template_dir / "base.html", 
        static_dir / "css" / "scanner.css",
        static_dir / "js" / "scanner-base.js",
        static_dir / "js" / "manual-control.js"
    ]
    
    missing_files = []
    for file_path in critical_files:
        if not file_path.exists():
            missing_files.append(file_path)
        else:
            print(f"   ✅ Found: {file_path.name}")
    
    if missing_files:
        print("❌ Missing critical web files:")
        for file_path in missing_files:
            print(f"   • {file_path}")
        return False
    else:
        print("✅ All critical web files present")
        return True

def main():
    """Main fix function"""
    print("🚀 Web Interface & Camera Fix Tool")
    print("=" * 50)
    
    # Fix camera streaming
    camera_fix = fix_camera_streaming()
    
    # Check web loading
    web_fix = fix_web_loading_issues()
    
    print("\n" + "=" * 50)
    print("📊 Fix Summary:")
    print(f"   • Camera Streaming: {'✅ Fixed' if camera_fix else '❌ Failed'}")
    print(f"   • Web Files: {'✅ OK' if web_fix else '❌ Missing'}")
    
    if camera_fix and web_fix:
        print("\n🎉 Fixes applied successfully!")
        print("\n📋 Next Steps:")
        print("   1. Restart web interface:")
        print("      python3 run_web_interface_fixed.py --mode production")
        print("   2. Test in browser: http://raspberrypi:8080")
        print("   3. Check camera streams in Manual Control tab")
    else:
        print("\n⚠️  Some fixes failed - check errors above")

if __name__ == "__main__":
    main()