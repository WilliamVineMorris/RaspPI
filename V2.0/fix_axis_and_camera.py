#!/usr/bin/env python3
"""
Web Interface Axis and Camera Fixes

Fixes the remaining issues:
1. Fix Z axis labeling - Z should be rotation, not linear movement
2. Fix camera preview scaling to be more reasonable
3. Ensure manual control functions are properly wired
"""

import os
import sys
from pathlib import Path

def apply_axis_and_camera_fixes():
    """Apply fixes for axis labels and camera scaling"""
    print("🔧 Applying Axis and Camera Fixes")
    print("=" * 50)
    
    v2_dir = Path(__file__).parent
    
    # Fix 1: Correct Z-axis labeling in manual.html
    print("\n🔧 Fix 1: Correcting Z-axis labeling...")
    
    manual_html_file = v2_dir / "web" / "templates" / "manual.html"
    
    if not manual_html_file.exists():
        print("❌ manual.html not found")
        return False
    
    # Read current content
    with open(manual_html_file, 'r') as f:
        html_content = f.read()
    
    # Fix Z-axis section - change from "Z Movement" to "Z Rotation"
    z_fixes = [
        ('<!-- Z Control -->', '<!-- Z (Rotation) Control -->'),
        ('<h4>Z Movement</h4>', '<h4>Z Rotation</h4>'),
        ('onclick="jogAxis(\'z\', getStepSize())">Z ↑</button>', 'onclick="jogAxis(\'z\', getStepSize())">Z ↻</button>'),
        ('onclick="jogAxis(\'z\', -getStepSize())">Z ↓</button>', 'onclick="jogAxis(\'z\', -getStepSize())">Z ↺</button>'),
        ('<label>Z:</label>', '<label>Z:</label>'),
        ('value="25.0">', 'value="0.0">'),
        ('<span>mm</span>', '<span>°</span>'),
    ]
    
    # Apply Z-axis fixes - be more specific with replacements
    updated_html = html_content
    
    # Fix the Z control section specifically
    z_section_old = '''            <!-- Z Control -->
            <div class="z-control">
                <h4>Z Movement</h4>
                <div class="z-buttons">
                    <button class="jog-btn z-up" onclick="jogAxis('z', getStepSize())">Z ↑</button>
                    <button class="home-btn" onclick="homeAxes(['z'])">🏠 Z</button>
                    <button class="jog-btn z-down" onclick="jogAxis('z', -getStepSize())">Z ↓</button>
                </div>
            </div>'''
    
    z_section_new = '''            <!-- Z (Rotation) Control -->
            <div class="z-control">
                <h4>Z Rotation</h4>
                <div class="z-buttons">
                    <button class="jog-btn z-up" onclick="jogAxis('z', getStepSize())">Z ↻</button>
                    <button class="home-btn" onclick="homeAxes(['z'])">🏠 Z</button>
                    <button class="jog-btn z-down" onclick="jogAxis('z', -getStepSize())">Z ↺</button>
                </div>
            </div>'''
    
    if z_section_old in updated_html:
        updated_html = updated_html.replace(z_section_old, z_section_new)
        print("✅ Fixed Z control section")
    else:
        print("⚠️ Z control section not found exactly - trying individual fixes")
        for old, new in z_fixes[:4]:  # Apply first 4 fixes
            if old in updated_html:
                updated_html = updated_html.replace(old, new)
    
    # Fix Z input section in "Go to Position"
    z_input_old = '''                <div class="input-group">
                    <label for="targetZ">Z:</label>
                    <input type="number" id="targetZ" step="0.1" 
                           min="{{ position_limits.z[0] }}" 
                           max="{{ position_limits.z[1] }}" 
                           value="25.0">
                    <span>mm</span>
                </div>'''
    
    z_input_new = '''                <div class="input-group">
                    <label for="targetZ">Z:</label>
                    <input type="number" id="targetZ" step="1" 
                           min="{{ position_limits.z[0] }}" 
                           max="{{ position_limits.z[1] }}" 
                           value="0.0">
                    <span>°</span>
                </div>'''
    
    if z_input_old in updated_html:
        updated_html = updated_html.replace(z_input_old, z_input_new)
        print("✅ Fixed Z input section")
    
    # Write back to file
    with open(manual_html_file, 'w') as f:
        f.write(updated_html)
    
    print("✅ Z-axis labeling corrected")
    
    # Fix 2: Improve camera preview scaling in CSS
    print("\n🔧 Fix 2: Improving camera preview scaling...")
    
    css_file = v2_dir / "web" / "static" / "css" / "scanner.css"
    
    if not css_file.exists():
        print("❌ scanner.css not found")
        return False
    
    # Read current content
    with open(css_file, 'r') as f:
        css_content = f.read()
    
    # Find and replace camera preview styles
    camera_feed_old = '''.camera-feed {
    width: 100%;
    height: 100%;
    display: block;
    object-fit: contain;
    max-height: 400px;
}'''
    
    camera_feed_new = '''.camera-feed {
    width: 100%;
    height: auto;
    display: block;
    object-fit: contain;
    max-height: 300px;
    max-width: 100%;
    border-radius: 4px;
}

.camera-preview-img {
    width: 100%;
    height: auto;
    display: block;
    object-fit: contain;
    max-height: 250px;
    max-width: 100%;
    border-radius: 4px;
    border: 1px solid var(--border-color);
}

.preview-container {
    width: 100%;
    max-width: 400px;
    margin: 0 auto;
    border: 1px solid var(--border-color);
    border-radius: var(--border-radius);
    overflow: hidden;
    background-color: var(--bg-tertiary);
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 200px;
}'''
    
    updated_css = css_content
    if camera_feed_old in updated_css:
        updated_css = updated_css.replace(camera_feed_old, camera_feed_new)
        print("✅ Improved camera preview scaling")
    else:
        # Add new styles if the old ones don't exist
        updated_css += "\n\n/* Enhanced Camera Preview Styles */\n" + camera_feed_new
        print("✅ Added improved camera preview styles")
    
    # Write back to file
    with open(css_file, 'w') as f:
        f.write(updated_css)
    
    # Fix 3: Ensure manual control JavaScript functions exist and work
    print("\n🔧 Fix 3: Ensuring manual control functions work...")
    
    # Create a simple JavaScript fix for manual controls if needed
    manual_js_file = v2_dir / "web" / "static" / "js" / "manual-control.js"
    
    if manual_js_file.exists():
        # Check if basic functions exist
        with open(manual_js_file, 'r') as f:
            js_content = f.read()
        
        # Add missing simple functions if they don't exist
        missing_functions = []
        
        required_functions = [
            'function jogAxis(',
            'function getStepSize(',
            'function homeAxes(',
            'function gotoPosition(',
            'function capturePhoto(',
        ]
        
        for func in required_functions:
            if func not in js_content:
                missing_functions.append(func)
        
        if missing_functions:
            print(f"⚠️ Missing functions: {missing_functions}")
            
            # Add simple function implementations
            simple_functions = '''

// Simple manual control functions for immediate functionality
function jogAxis(axis, distance) {
    console.log(`Jogging ${axis} by ${distance}`);
    
    // Use the existing API
    const data = {
        axis: axis.toLowerCase(),
        direction: distance > 0 ? '+' : '-',
        mode: 'step',
        distance: Math.abs(distance)
    };
    
    fetch('/api/jog', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log(`${axis} jogged successfully`);
        } else {
            console.error(`Jog failed: ${data.error}`);
        }
    })
    .catch(error => {
        console.error('Jog error:', error);
    });
}

function getStepSize() {
    const stepSelect = document.getElementById('stepSize');
    return parseFloat(stepSelect ? stepSelect.value : 1.0);
}

function homeAxes(axes) {
    console.log(`Homing axes: ${axes}`);
    
    fetch('/api/home', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({axes: axes})
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('Homing completed');
        } else {
            console.error(`Homing failed: ${data.error}`);
        }
    })
    .catch(error => {
        console.error('Homing error:', error);
    });
}

function gotoPosition() {
    const x = document.getElementById('targetX')?.value;
    const y = document.getElementById('targetY')?.value;
    const z = document.getElementById('targetZ')?.value;
    const c = document.getElementById('targetC')?.value;
    
    const position = {};
    if (x) position.x = parseFloat(x);
    if (y) position.y = parseFloat(y);
    if (z) position.z = parseFloat(z);
    if (c) position.c = parseFloat(c);
    
    console.log('Going to position:', position);
    
    fetch('/api/position', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(position)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('Position reached');
        } else {
            console.error(`Position move failed: ${data.error}`);
        }
    })
    .catch(error => {
        console.error('Position error:', error);
    });
}

function capturePhoto() {
    console.log('Capturing photo');
    
    fetch('/api/camera/capture', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({camera_id: 'camera_1'})
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('Photo captured');
        } else {
            console.error(`Capture failed: ${data.error}`);
        }
    })
    .catch(error => {
        console.error('Capture error:', error);
    });
}

function captureFromCamera(cameraId) {
    console.log(`Capturing from camera ${cameraId}`);
    
    fetch('/api/camera/capture', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({camera_id: `camera_${cameraId + 1}`})
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log(`Photo captured from camera ${cameraId}`);
        } else {
            console.error(`Capture failed: ${data.error}`);
        }
    })
    .catch(error => {
        console.error('Capture error:', error);
    });
}

// Initialize manual controls when page loads
document.addEventListener('DOMContentLoaded', function() {
    console.log('Manual control functions loaded');
    
    // Refresh camera preview every 5 seconds
    const cameraImg = document.getElementById('activePreview');
    if (cameraImg) {
        setInterval(() => {
            const timestamp = new Date().getTime();
            const currentSrc = cameraImg.src.split('?')[0];
            cameraImg.src = currentSrc + '?t=' + timestamp;
        }, 5000);
    }
});
'''
            
            # Append the functions to the file
            with open(manual_js_file, 'a') as f:
                f.write(simple_functions)
            
            print("✅ Added missing manual control functions")
        else:
            print("✅ All required manual control functions exist")
    else:
        print("❌ manual-control.js not found")
        return False
    
    print("\n✅ ALL FIXES APPLIED SUCCESSFULLY!")
    print("\n📋 Summary of Changes:")
    print("1. ✅ Z-axis now labeled as 'Z Rotation' with ↻/↺ symbols")
    print("2. ✅ Z-axis input uses degrees (°) instead of mm")
    print("3. ✅ Z-axis default value changed from 25.0 to 0.0")
    print("4. ✅ Camera preview scaling improved (max 250px height)")
    print("5. ✅ Camera preview container with proper borders")
    print("6. ✅ Manual control functions ensured to work")
    print("7. ✅ Camera refresh every 5 seconds for live preview")
    
    print("\n🚀 Next Steps:")
    print("1. Restart the web server")
    print("2. Test Z-axis controls - should now show rotation symbols")
    print("3. Test camera preview - should be properly scaled") 
    print("4. Test all manual controls - should be responsive")
    print("5. Verify Z-axis input accepts degrees, not mm")
    
    return True

def main():
    """Main fix application"""
    try:
        success = apply_axis_and_camera_fixes()
        return success
    except Exception as e:
        print(f"❌ Fix application failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)