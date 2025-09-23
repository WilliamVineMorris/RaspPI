#!/usr/bin/env python3
"""
Web Interface Bug Fixes

Fixes identified issues:
1. Missing /api/jog endpoint causing manual controls to fail
2. Multiple "homing in progress" messages due to overly complex polling
"""

import os
import sys
from pathlib import Path

def apply_web_interface_fixes():
    """Apply fixes to web interface"""
    print("🔧 Applying Web Interface Bug Fixes")
    print("=" * 50)
    
    v2_dir = Path(__file__).parent
    
    # Fix 1: Add missing /api/jog endpoint to web_interface.py
    print("\n🔧 Fix 1: Adding missing /api/jog endpoint...")
    
    web_interface_file = v2_dir / "web" / "web_interface.py"
    
    if not web_interface_file.exists():
        print("❌ web/web_interface.py not found")
        return False
    
    # Read current content
    with open(web_interface_file, 'r') as f:
        content = f.read()
    
    # Check if /api/jog already exists
    if '/api/jog' in content:
        print("✅ /api/jog endpoint already exists")
    else:
        # Find the position to insert the new endpoint (after /api/move)
        move_endpoint_pos = content.find('@self.app.route(\'/api/move\', methods=[\'POST\'])')
        if move_endpoint_pos != -1:
            # Find the end of the move function
            next_route_pos = content.find('@self.app.route', move_endpoint_pos + 1)
            if next_route_pos != -1:
                jog_endpoint_code = '''
        @self.app.route('/api/jog', methods=['POST'])
        def api_jog():
            """Handle jog movement commands"""
            try:
                data = request.get_json() or {}
                
                # Validate jog parameters
                axis = data.get('axis', '').lower()
                direction = data.get('direction', '')
                mode = data.get('mode', 'step')
                distance = data.get('distance', 1.0)
                speed = data.get('speed', 10.0)
                
                if axis not in ['x', 'y', 'z', 'c']:
                    return jsonify({"success": False, "error": "Invalid axis"}), 400
                
                if direction not in ['+', '-']:
                    return jsonify({"success": False, "error": "Invalid direction"}), 400
                
                # Convert to move command format
                move_data = {}
                move_distance = distance if direction == '+' else -distance
                move_data[axis] = move_distance
                
                if mode == 'continuous':
                    # For continuous jog, use smaller increments
                    move_data[axis] = 0.5 if direction == '+' else -0.5
                
                # Execute the movement using existing move logic
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(self._handle_move_async(move_data))
                loop.close()
                
                return jsonify(result)
                
            except Exception as e:
                logger.error(f"Jog command error: {e}")
                return jsonify({"success": False, "error": str(e)}), 500

        @self.app.route('/api/stop', methods=['POST'])
        def api_stop():
            """Handle motion stop commands"""
            try:
                # Use emergency stop for immediate halt
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(self.orchestrator.emergency_stop())
                loop.close()
                
                return jsonify({"success": True, "message": "Motion stopped"})
                
            except Exception as e:
                logger.error(f"Stop command error: {e}")
                return jsonify({"success": False, "error": str(e)}), 500

'''
                # Insert the new endpoint code
                new_content = content[:next_route_pos] + jog_endpoint_code + "\n        " + content[next_route_pos:]
                
                # Write back to file
                with open(web_interface_file, 'w') as f:
                    f.write(new_content)
                
                print("✅ Added /api/jog and /api/stop endpoints")
            else:
                print("❌ Could not find insertion point for /api/jog endpoint")
                return False
        else:
            print("❌ Could not find /api/move endpoint to insert after")
            return False
    
    # Fix 2: Simplify homing progress logic in manual-control.js
    print("\n🔧 Fix 2: Simplifying homing progress logic...")
    
    manual_js_file = v2_dir / "web" / "static" / "js" / "manual-control.js"
    
    if not manual_js_file.exists():
        print("❌ manual-control.js not found")
        return False
    
    # Read current content
    with open(manual_js_file, 'r') as f:
        js_content = f.read()
    
    # Create simplified homing function
    simplified_homing = '''    /**
     * Home all axes with simplified progress monitoring
     */
    async homeAllAxes() {
        if (!confirm('Home all axes? This will move all axes to their reference positions.')) {
            return;
        }

        const homeButton = document.querySelector('[onclick*="homeAllAxes"]') || 
                          document.getElementById('homeAllAxes') ||
                          document.querySelector('button[title*="home"]');
        let progressInterval = null;
        let startTime = Date.now();
        
        try {
            // Disable button and show immediate feedback
            if (homeButton) {
                homeButton.disabled = true;
                homeButton.textContent = '🏠 Homing...';
                homeButton.style.opacity = '0.6';
            }

            ScannerBase.showLoading('🏠 Starting homing sequence...');
            ScannerBase.addLogEntry('🚀 Homing all axes...', 'info');

            // Start the homing request
            const response = await ScannerBase.apiRequest('/api/home', {
                method: 'POST'
            });

            ScannerBase.addLogEntry('⏳ Homing request sent - monitoring progress...', 'info');

            // Simplified progress monitoring - check every 2 seconds
            let checkCount = 0;
            const maxChecks = 90; // 3 minutes timeout
            
            progressInterval = setInterval(async () => {
                checkCount++;
                const elapsed = Math.round((Date.now() - startTime) / 1000);
                
                try {
                    // Get current status
                    const status = await ScannerBase.apiRequest('/api/status');
                    const motionState = status.motion?.status || 'unknown';
                    const isHomed = status.motion?.homed || status.motion?.is_homed || false;
                    
                    // Update progress display
                    ScannerBase.showLoading(`🏠 Homing in progress... (${elapsed}s)`);
                    
                    // Check for completion - simple criteria
                    if (motionState === 'idle' && isHomed && elapsed > 30) {
                        // Homing completed
                        clearInterval(progressInterval);
                        progressInterval = null;
                        
                        ScannerBase.hideLoading();
                        ScannerBase.showAlert('🎉 All axes homed successfully!', 'success', 3000, false);
                        ScannerBase.addLogEntry(`✅ Homing completed in ${elapsed} seconds`, 'success');
                        
                        // Re-enable button
                        if (homeButton) {
                            homeButton.disabled = false;
                            homeButton.textContent = homeButton.dataset.originalText || '🏠 Home All';
                            homeButton.style.opacity = '1';
                        }
                        
                        // Update position displays
                        this.updatePositionDisplays(status.motion.position);
                        return;
                    }
                    
                    // Timeout check
                    if (checkCount >= maxChecks) {
                        throw new Error('Homing timeout after 3 minutes');
                    }
                    
                } catch (error) {
                    if (progressInterval) {
                        clearInterval(progressInterval);
                        progressInterval = null;
                    }
                    
                    ScannerBase.hideLoading();
                    ScannerBase.showAlert(`Homing error: ${error.message}`, 'error');
                    ScannerBase.addLogEntry(`❌ Homing failed: ${error.message}`, 'error');
                    
                    // Re-enable button
                    if (homeButton) {
                        homeButton.disabled = false;
                        homeButton.textContent = homeButton.dataset.originalText || '🏠 Home All';
                        homeButton.style.opacity = '1';
                    }
                }
            }, 2000); // Check every 2 seconds
            
        } catch (error) {
            if (progressInterval) {
                clearInterval(progressInterval);
            }
            
            ScannerBase.hideLoading();
            ScannerBase.showAlert(`Homing failed: ${error.message}`, 'error');
            ScannerBase.addLogEntry(`❌ Homing failed: ${error.message}`, 'error');
            
            // Re-enable button
            if (homeButton) {
                homeButton.disabled = false;
                homeButton.textContent = homeButton.dataset.originalText || '🏠 Home All';
                homeButton.style.opacity = '1';
            }
        }
    },'''
    
    # Find and replace the existing homeAllAxes function
    start_pattern = 'async homeAllAxes() {'
    start_pos = js_content.find(start_pattern)
    
    if start_pos != -1:
        # Find the end of the function (next function or end of object)
        brace_count = 0
        pos = start_pos + len(start_pattern)
        in_function = True
        
        while pos < len(js_content) and in_function:
            char = js_content[pos]
            if char == '{':
                brace_count += 1
            elif char == '}':
                if brace_count == 0:
                    # Found the closing brace of the function
                    end_pos = pos + 1
                    in_function = False
                else:
                    brace_count -= 1
            pos += 1
        
        if not in_function:
            # Replace the function
            new_js_content = js_content[:start_pos] + simplified_homing + js_content[end_pos:]
            
            # Write back to file
            with open(manual_js_file, 'w') as f:
                f.write(new_js_content)
            
            print("✅ Simplified homing progress logic")
        else:
            print("❌ Could not find end of homeAllAxes function")
            return False
    else:
        print("❌ Could not find homeAllAxes function")
        return False
    
    print("\n✅ ALL FIXES APPLIED SUCCESSFULLY!")
    print("\n🚀 Next Steps:")
    print("1. Restart the web server")
    print("2. Test manual controls - buttons should now work")
    print("3. Test homing - should show single progress message")
    print("4. Manual movement controls should be responsive")
    
    return True

def main():
    """Main fix application"""
    try:
        success = apply_web_interface_fixes()
        return success
    except Exception as e:
        print(f"❌ Fix application failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)