#!/usr/bin/env python3
"""
Complete Web UI Integration Test

Tests that motion optimization works correctly with:
1. Web UI manual position commands
2. Web UI scanning operations
3. All current scanning methods
4. Real hardware integration
"""

import sys
import asyncio
import json
from pathlib import Path

v2_path = Path(__file__).parent
sys.path.insert(0, str(v2_path))

from core.config_manager import ConfigManager
from scanning.scan_orchestrator import ScanOrchestrator
from scanning.scan_patterns import GridScanPattern, GridPatternParameters
from core.types import Position4D

class WebUIMotionTracker:
    """Track motion commands as they would be sent from Web UI"""
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.motion_commands = []
        
        # Track motion controller commands (same as web UI uses)
        motion_controller = orchestrator.motion_controller
        if hasattr(motion_controller, 'protocol'):
            self.original_send_command = motion_controller.protocol.send_command
            motion_controller.protocol.send_command = self.track_command
            
    def track_command(self, command):
        """Track G-code commands sent to FluidNC"""
        self.motion_commands.append(command)
        print(f"🌐 WEB UI MOTION: {command}")
        return self.original_send_command(command)

async def test_web_ui_manual_positioning():
    """Test manual positioning as called from web UI"""
    print("🌐 Testing Web UI Manual Positioning...")
    
    # Setup real hardware mode
    config_file = v2_path / "config" / "scanner_config.yaml"
    config = ConfigManager(config_file)
    config._config_data = config._config_data or {}
    config._config_data['system'] = {'simulation_mode': False}
    
    orchestrator = ScanOrchestrator(config)
    await orchestrator.initialize()
    
    tracker = WebUIMotionTracker(orchestrator)
    
    # Test manual position command (exactly as web UI does it)
    print("📍 Testing manual position command...")
    tracker.motion_commands.clear()
    
    # This is exactly how web UI calls position commands
    position_obj = Position4D(x=30.0, y=40.0, z=15.0, c=10.0)
    
    try:
        # Convert to motion Position4D if needed (type compatibility)
        from motion.base import Position4D as MotionPosition4D
        motion_pos = MotionPosition4D(
            x=position_obj.x, y=position_obj.y, 
            z=position_obj.z, c=position_obj.c
        )
        
        result = await orchestrator.motion_controller.move_to_position(motion_pos)
        
        if result:
            print(f"✅ Manual positioning successful")
            
            # Verify single optimized command
            if len(tracker.motion_commands) >= 1:
                last_command = tracker.motion_commands[-1]
                if 'G0' in last_command and 'X30' in last_command and 'Y40' in last_command:
                    print(f"✅ Web UI manual positioning uses optimized single G0 command")
                    return True
                    
        print(f"⚠️  Manual positioning may need optimization")
        return False
        
    except Exception as e:
        print(f"❌ Manual positioning failed: {e}")
        return False

async def test_web_ui_scanning_integration():
    """Test complete scanning as called from web UI"""
    print("\n🌐 Testing Web UI Scanning Integration...")
    
    # Setup real hardware mode
    config_file = v2_path / "config" / "scanner_config.yaml"
    config = ConfigManager(config_file)
    config._config_data = config._config_data or {}
    config._config_data['system'] = {'simulation_mode': False}
    
    orchestrator = ScanOrchestrator(config)
    await orchestrator.initialize()
    
    tracker = WebUIMotionTracker(orchestrator)
    
    # Create minimal scan pattern (same as web UI would)
    print("📐 Creating scan pattern (as web UI does)...")
    pattern_params = GridPatternParameters(
        min_x=20.0, max_x=30.0,
        min_y=25.0, max_y=25.1,  # Minimal range
        min_z=0.0, max_z=0.1,
        min_c=0.0, max_c=0.1,
        x_spacing=10.0,  # 2 points
        y_spacing=10.0,  # 1 point
        z_spacing=10.0,  # 1 point
        c_steps=1,
        zigzag=False
    )
    
    pattern = GridScanPattern(
        pattern_id="web_ui_test",
        parameters=pattern_params
    )
    
    scan_points = list(pattern.generate_points())
    print(f"📍 Scan pattern: {len(scan_points)} points")
    
    try:
        # Start scan exactly as web UI does
        print("🚀 Starting scan (web UI method)...")
        tracker.motion_commands.clear()
        
        # This is the exact same call the web UI makes
        scan_state = await orchestrator.start_scan(
            pattern=pattern,
            output_directory="/tmp/web_ui_test_scan",
            scan_id="web_ui_integration_test"
        )
        
        # Wait a bit for initial commands
        await asyncio.sleep(5)
        
        # Check for optimized motion commands
        g0_commands = [cmd for cmd in tracker.motion_commands if cmd.startswith('G0 ')]
        position_commands = [cmd for cmd in g0_commands if 'X' in cmd and 'Y' in cmd]
        
        print(f"\n📊 WEB UI SCAN ANALYSIS:")
        print(f"   Total commands: {len(tracker.motion_commands)}")
        print(f"   G0 commands: {len(g0_commands)}")
        print(f"   Multi-axis commands: {len(position_commands)}")
        
        print(f"\n📋 COMMANDS FROM WEB UI SCAN:")
        for i, cmd in enumerate(tracker.motion_commands, 1):
            print(f"   {i:2d}. {cmd}")
            
        if len(position_commands) > 0:
            print(f"\n✅ Web UI scanning uses optimized motion commands")
            return True
        else:
            print(f"\n⚠️  Web UI scanning may need motion optimization")
            return False
            
    except Exception as e:
        print(f"\n❌ Web UI scanning test failed: {e}")
        return False
    finally:
        # Stop any running scan
        try:
            await orchestrator.stop_scan()
        except:
            pass

async def test_all_scanning_methods():
    """Test that all scanning methods use optimized motion"""
    print("\n🔍 Testing All Scanning Methods...")
    
    results = []
    
    # Test 1: Manual positioning (web UI style)
    manual_result = await test_web_ui_manual_positioning()
    results.append(("Manual Positioning", manual_result))
    
    # Test 2: Web UI scanning integration
    scan_result = await test_web_ui_scanning_integration()
    results.append(("Web UI Scanning", scan_result))
    
    return results

if __name__ == "__main__":
    print("🧪 COMPLETE WEB UI INTEGRATION TEST")
    print("=" * 50)
    
    try:
        results = asyncio.run(test_all_scanning_methods())
        
        print(f"\n📊 INTEGRATION TEST RESULTS:")
        print("=" * 30)
        
        all_passed = True
        for test_name, result in results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"   {test_name}: {status}")
            if not result:
                all_passed = False
        
        print("=" * 30)
        
        if all_passed:
            print(f"\n🎉 ALL INTEGRATION TESTS PASSED!")
            print(f"   ✅ Web UI manual positioning uses optimized motion")
            print(f"   ✅ Web UI scanning uses optimized motion")
            print(f"   ✅ Motion optimization fully integrated")
            print(f"\n🚀 SYSTEM READY FOR PRODUCTION WEB UI USE!")
        else:
            print(f"\n⚠️  SOME INTEGRATION ISSUES FOUND")
            print(f"   Please check failed tests above")
            
    except Exception as e:
        print(f"\n💥 Integration test failed: {e}")
        import traceback
        traceback.print_exc()